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

from finding_identity import finding_identity

AUDIT_RULINGS = ("discharged", "not-discharged", "discharged-but-new-issue")

UNAUTHENTICATED_NO_AUDITOR_RECORDED = "no-auditor-recorded"
UNAUTHENTICATED_MANIFEST_ENTRY_MISSING = "manifest-entry-missing"
UNAUTHENTICATED_MANIFEST_VENDOR_MISMATCH = "manifest-vendor-mismatch"
UNAUTHENTICATED_CAUSES = (
    UNAUTHENTICATED_NO_AUDITOR_RECORDED,
    UNAUTHENTICATED_MANIFEST_ENTRY_MISSING,
    UNAUTHENTICATED_MANIFEST_VENDOR_MISMATCH,
)

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


def has_usable_new_issues(candidates):
    """True when `candidates` carries at least one dict-shaped new-issue candidate — EXACTLY the
    usability test `apply_audit_results` applies to a `discharged-but-new-issue` claim, exposed so
    the submit-shape guard (#885) and the fold can never read the field differently. The guard's
    whole value is that what it accepts is what the fold can use."""
    return bool(_valid_new_issues(candidates, None))


def has_usable_reason(reason):
    """True when `reason` is a non-blank string — EXACTLY the grounds test `apply_audit_results`
    applies before it honors a `discharged` ruling, exposed so the submit-shape guard (#885) and the
    fold can never read the field differently. Sibling of `has_usable_new_issues`: the guard's whole
    value is that what it accepts is what the fold can use, so a later loosening or tightening of the
    rule moves BOTH sides at once — a guard reading it one way and the fold the other either
    false-refuses a legitimate submit or re-admits the #885 terminal-loss class."""
    return isinstance(reason, str) and bool(reason.strip())


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


def has_usable_unnamed_change(value):
    """True when `value` is a non-blank string — the auditor's plain-words statement of behaviour the
    fix changes that its finding does not name. Absent, null or blank means none."""
    return isinstance(value, str) and bool(value.strip())


# The reason an audit entry carries when no result came back for its target (silence, not a ruling).
NO_AUDIT_RESULT_REASON = "no audit result for this finding — cannot certify the fix discharged"


def apply_audit_results(audited, results, expected_auditors=None, collection_manifest=None,
                        carry_fields=(), change_allowed_ids=()):
    """Consume per-finding fix-audit rulings; fail-closed on ambiguity, silence, and malformation.

    `audited`  — findings already carrying a unique staged `id` (via verification.stage_ids)
                 plus file/line/title/severity.
    `results`  — audit-result dicts {id, ruling, reason, evidence?, newIssues?, auditorVendor?}.
                 The in-result `auditorVendor` is ADVISORY only — a claimant-controlled echo that
                 authenticates NOTHING (a fixer or misrouted worker can echo the expected vendor).
    `expected_auditors` — {finding_id: auditor_vendor} recorded by the DRIVER
                 (round_driver._audit_targets) naming the SELECTED independent auditor per target.
                 When None, the target's driver-stamped `auditorVendor` is the fallback selection; a
                 target with neither is not provenance-enforced.
    `collection_manifest` — {result_id: vendor} the DISPATCHING ORCHESTRATOR recorded from its OWN
                 dispatch records, out-of-band from the results (round_driver threads the submit
                 artifact's `collectionManifest`; the library run_loop synthesizes it from the
                 dispatch payload). This — NOT the result's echo — is the trusted provenance: a
                 clearing ruling is authenticated iff `manifest[id]` EXISTS and EQUALS the recorded
                 selected auditor. Provenance rests on the orchestrator's dispatch manifest; the fold
                 cannot cryptographically verify engine identity and does not pretend to.

    `change_allowed_ids` — target ids whose finding carries a ruling that allows the fix to change
                 behaviour the finding does not name. A clearing result that states such a change
                 (`unnamedChange`) stays discharged only for these ids (its audit entry records
                 `allowedChange`); for any other id it is `not-discharged` and listed in
                 `unnamedChange`. A non-string, non-null `unnamedChange` is malformed.

    Returns {audits, discharged, notDischarged, newIssues, unaudited, ambiguous, malformed,
    unmatched, unauthenticated, echoMismatch, unnamedChange}. Each `audits` entry carries the EFFECTIVE
    (post-fail-closed) ruling. The disclosure lists (unaudited/ambiguous/malformed/unauthenticated)
    are subsets of notDischarged that name WHY the finding could not be certified discharged;
    `unmatched` names results that hit no finding. `unauthenticated` names clearing rulings the
    orchestrator's manifest could not authenticate (missing entry, or manifest ≠ the selected
    independent auditor). `echoMismatch` names discharged findings whose advisory in-result echo
    disagreed with the governing manifest (disclosed, but the manifest governed → still discharged).
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

    # Duplicate TARGET ids (e.g. a session persisted before per-location ids) — honor none of the
    # group so one ruling cannot discharge an unaudited sibling.
    duplicate_target_ids = set()
    target_id_counts = {}
    for f in audited:
        if not isinstance(f, dict):
            continue
        fid = f.get("id")
        if isinstance(fid, str):
            target_id_counts[fid] = target_id_counts.get(fid, 0) + 1
    for fid, count in target_id_counts.items():
        if count > 1:
            duplicate_target_ids.add(fid)
    ambiguous_ids |= duplicate_target_ids

    audits = []
    discharged, not_discharged = [], []
    new_issues = []
    unaudited, malformed = [], []
    unauthenticated = []
    echo_mismatch = []
    unnamed_change = []
    allowed_ids = set(i for i in (change_allowed_ids or ()) if isinstance(i, str))
    matched_ids = set()

    def _reject_unauthenticated(base, fid, reason, cause):
        """Fail-closed a clearing ruling the orchestrator's manifest could not authenticate:
        not-discharged, disclosed as `unauthenticated`."""
        if fid is not None:
            unauthenticated.append(fid)
            not_discharged.append(fid)
        base.update(ruling="not-discharged", reason=reason, unauthenticatedCause=cause)
        audits.append(base)

    def refuse_unnamed_change(base, fid, text, candidates):
        """A clearing result that states behaviour its finding does not name, with no ruling that
        allows it: not-discharged, disclosed as `unnamedChange`; any new issues it carried stay."""
        if fid is not None:
            unnamed_change.append(fid)
            not_discharged.append(fid)
        new_issues.extend(candidates)
        base.update(ruling="not-discharged",
                    reason="the fix changes behaviour its finding does not name: %s" % text)
        audits.append(base)

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
        ident = f.get("identity")
        if not isinstance(ident, str) or not ident:
            ident = finding_identity(f) if isinstance(f, dict) else None
        base = {"id": fid, "identity": ident, "file": f.get("file"), "line": f.get("line"),
                "title": f.get("title"), "classKey": f.get("classKey"),
                "dimension": f.get("dimension"), "taxonomy": f.get("taxonomy")}
        for name in carry_fields:
            marker = f.get(name)
            if isinstance(marker, str) and marker:
                base[name] = marker

        # No matching result (silence) → fail-closed not-discharged, disclosed as unaudited.
        # An ambiguous id is IN seen_ids OR is a duplicate target id — disclosed via `ambiguous`.
        if r is None:
            if fid is not None and fid in duplicate_target_ids:
                base.update(ruling="not-discharged",
                            reason="duplicate audit target id — honoring none")
            elif fid is not None and fid in ambiguous_ids:
                base.update(ruling="not-discharged",
                            reason="more than one audit result claimed this finding — honoring none")
            else:
                if fid is not None:
                    unaudited.append(fid)
                base.update(ruling="not-discharged",
                            reason=NO_AUDIT_RESULT_REASON)
            audits.append(base)
            if fid is not None:
                not_discharged.append(fid)
            continue

        if fid is not None and fid in duplicate_target_ids:
            base.update(ruling="not-discharged",
                        reason="duplicate audit target id — honoring none")
            audits.append(base)
            not_discharged.append(fid)
            continue

        ruling = r.get("ruling")
        reason = r.get("reason")
        # The SHARED grounds predicate — the same function the submit-shape guard calls, never a
        # second copy of the rule (#885 review: cross-module connascence of algorithm).
        has_reason = has_usable_reason(reason)
        evidence = r.get("evidence")

        # Provenance (trust-boundary): a ruling that CLEARS the finding is authenticated against the
        # dispatching ORCHESTRATOR's out-of-band COLLECTION MANIFEST — {result-id: vendor} recorded
        # from the orchestrator's OWN dispatch records, NEVER derived from the result's contents. The
        # in-result `auditorVendor` echo is ADVISORY only: a forged/mistaken result simply echoes the
        # expected value, so the echo authenticates nothing (the R2 defect: the auditor's own words
        # used as their credential). Fail-closed rejections (each → not-discharged + disclosed as
        # `unauthenticated`): a target with NO recorded auditor selection cannot prove independence at
        # all; NO manifest entry means the orchestrator never recorded who executed this audit; a
        # manifest vendor that disagrees with the recorded selection is a misroute. When authenticated
        # by the manifest, an echo that disagrees with it is disclosed via `echoMismatch` but the
        # manifest governs — the discharge stands.
        if provenance_enforced and ruling in ("discharged", "discharged-but-new-issue"):
            if not expected_auditor:
                _reject_unauthenticated(
                    base, fid,
                    "no independent auditor was recorded for this target — cannot prove the audit "
                    "came from an independent auditor; treated as not-discharged",
                    UNAUTHENTICATED_NO_AUDITOR_RECORDED)
                continue
            manifest_vendor = None
            if isinstance(collection_manifest, dict) and fid is not None:
                mv = collection_manifest.get(fid)
                if isinstance(mv, str) and mv:
                    manifest_vendor = mv
            if manifest_vendor is None:
                _reject_unauthenticated(
                    base, fid,
                    "no dispatch-manifest entry for this target — the orchestrator did not record "
                    "which engine executed the audit; cannot authenticate; treated as not-discharged",
                    UNAUTHENTICATED_MANIFEST_ENTRY_MISSING)
                continue
            if manifest_vendor != expected_auditor:
                _reject_unauthenticated(
                    base, fid,
                    "the dispatch manifest names %r but the selected independent auditor is %r — "
                    "treated as not-discharged" % (manifest_vendor, expected_auditor),
                    UNAUTHENTICATED_MANIFEST_VENDOR_MISMATCH)
                continue
            # Authenticated by the orchestrator's manifest. The recorded auditor is the TRUSTED value
            # (the manifest, not the claimant echo). An echo that disagrees is advisory noise —
            # disclosed via `echoMismatch`, but the manifest governs and the discharge stands.
            base["auditor"] = manifest_vendor
            echo = r.get("auditorVendor")
            if isinstance(echo, str) and echo and echo != manifest_vendor:
                if fid is not None:
                    echo_mismatch.append(fid)
                base["echoMismatch"] = {"echo": echo, "manifest": manifest_vendor}

        # A clearing result that names behaviour its finding does not name is accepted only when the
        # finding's ruling allows the change. Provenance (above) keeps its precedence.
        unnamed = r.get("unnamedChange")
        if ruling in _CLEARS and unnamed is not None and not isinstance(unnamed, str):
            if fid is not None:
                malformed.append(fid)
            base.update(ruling="not-discharged",
                        reason="`unnamedChange` is not a string — treated as not-discharged")
            audits.append(base)
            if fid is not None:
                not_discharged.append(fid)
            continue
        unnamed_text = unnamed.strip() if has_usable_unnamed_change(unnamed) else None

        if ruling == "discharged":
            if has_reason and unnamed_text and fid not in allowed_ids:
                refuse_unnamed_change(base, fid, unnamed_text, [])
                continue
            if has_reason:
                if unnamed_text:
                    base["allowedChange"] = unnamed_text
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
            if candidates and unnamed_text and fid not in allowed_ids:
                refuse_unnamed_change(base, fid, unnamed_text, candidates)
                continue
            if candidates:
                if unnamed_text:
                    base["allowedChange"] = unnamed_text
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
            mv = collection_manifest.get(fid) if isinstance(collection_manifest, dict) else None
            if isinstance(mv, str) and mv and mv == expected_auditor:
                base["auditor"] = mv  # a completed rejection by the selected auditor is a reviewer that ran
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
        "echoMismatch": echo_mismatch,
        "unnamedChange": unnamed_change,
    }
