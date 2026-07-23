#!/usr/bin/env python3
"""Deterministic consumer of the per-finding verification stage (#506).

Sibling of loop_synthesis.py: applies a review panel's per-finding verification verdicts
(CONFIRMED / PLAUSIBLE / REFUTED) deterministically so accounting stays reproducible even
though a model made the judgments. stdlib only; never raises on bad input; fail-closed —
a model's silence or malformed verdict never drops a finding.
"""
import circuit_breaker
import panel_tally

VERDICTS = ("CONFIRMED", "PLAUSIBLE", "REFUTED")
_TIERS = ("Critical", "Important", "Minor", "Nit")
_DEFAULT_BLOCKING_SEVERITY = "Important"
CLUSTER_LINE_SPAN = 100
_SEV_RANK = {"Critical": 0, "Important": 1, "Minor": 2, "Nit": 3}
_BODY_SEP = "\n\n---\n\n"


def stage_ids(findings):
    """Return shallow copies with guaranteed-unique staged ids v0..vN."""
    if not isinstance(findings, list):
        return []
    staged = []
    for index, f in enumerate(findings):
        if not isinstance(f, dict):
            staged.append({"id": f"v{index}"})
            continue
        copy = dict(f)
        copy["id"] = f"v{index}"
        staged.append(copy)
    return staged


def cluster_findings(findings):
    """Group id-staged findings by (file, line // CLUSTER_LINE_SPAN) for verifier dispatch."""
    if not isinstance(findings, list):
        return []
    buckets = {}
    order = []
    for f in findings:
        if not isinstance(f, dict):
            continue
        file = f.get("file") or ""
        line = f.get("line") or 0
        try:
            bucket = int(line) // CLUSTER_LINE_SPAN
        except (TypeError, ValueError):
            bucket = 0
        key = (file, bucket)
        if key not in buckets:
            buckets[key] = []
            order.append(key)
        buckets[key].append(f)
    order.sort(key=lambda k: (k[0], k[1]))
    clusters = []
    for file, bucket in order:
        group = buckets[(file, bucket)]
        clusters.append({
            "key": f"{file}:{bucket}",
            "findings": list(group),
            "ids": [f.get("id") for f in group if isinstance(f.get("id"), str)],
        })
    return clusters


def _kept_severity(f, v, honored):
    """Resolve the kept finding's severity, fail-closed.

    A verdict's `severity` is honored ONLY when the verdict itself is honored (a valid
    CONFIRMED/PLAUSIBLE). For KEEP-ON-UNCERTAIN (no/unknown verdict, reasonless-REFUTED,
    ambiguous) the finding keeps its own pre-verification severity; an off-scale/missing
    severity with no honored verdict falls to the blocking floor, never silently "Nit".
    """
    if honored:
        verdict_severity = v.get("severity") if isinstance(v, dict) else None
        if verdict_severity in _TIERS:
            return verdict_severity
    finding_severity = f.get("severity")
    if finding_severity in _TIERS:
        return finding_severity
    return _DEFAULT_BLOCKING_SEVERITY


def apply_verdicts(findings, verdicts):
    """Consume per-finding verification verdicts; fail-closed on ambiguity."""
    # Build the id→verdict map, detecting duplicate ids. A finding id carried by MORE THAN
    # ONE verdict is ambiguous — honor none of them (KEEP-ON-UNCERTAIN) so a later
    # REFUTED can't silently win and drop the finding. `seen_ids` is every id that appeared
    # in any verdict (used to tell silence from a matched-but-unhonored verdict).
    by_id = {}
    seen_ids = set()
    ambiguous_ids = set()
    if isinstance(verdicts, list):
        for v in verdicts:
            if isinstance(v, dict) and isinstance(v.get("id"), str):
                vid = v["id"]
                if vid in seen_ids:
                    ambiguous_ids.add(vid)
                    by_id.pop(vid, None)
                    continue
                seen_ids.add(vid)
                by_id[vid] = v
    if not isinstance(findings, list):
        findings = []
    matched_ids = set()
    survivors, drops, downgrades = [], [], []
    unverified = []
    for f in findings:
        if not isinstance(f, dict):
            continue
        fid = f.get("id")
        if not isinstance(fid, str):
            fid = None
        v = by_id.get(fid) if fid is not None else None
        if v is not None and fid is not None:
            matched_ids.add(fid)
        # Disclose silence: a finding whose id no verdict ever carried (verifier silence /
        # a lost verdict). Ambiguous ids ARE in seen_ids, so they never count as silent —
        # they are disclosed via `ambiguous` instead.
        if fid is not None and fid not in seen_ids:
            unverified.append(fid)
        verdict = v.get("verdict") if isinstance(v, dict) else None
        reason = v.get("reason") if isinstance(v, dict) else None
        if verdict == "REFUTED" and isinstance(reason, str) and reason.strip():
            drops.append({
                "id": fid,
                "file": f.get("file"),
                "title": f.get("title"),
                "reason": reason.strip(),
                "was_blocking_tagged": circuit_breaker.is_blocking(f.get("severity")),
            })
            continue
        # A verdict is HONORED only when it is a valid CONFIRMED/PLAUSIBLE. Everything
        # else (no verdict, unknown value, reasonless-REFUTED, ambiguous → v is None) is
        # KEEP-ON-UNCERTAIN and must not apply the rejected verdict's severity.
        honored = verdict in ("CONFIRMED", "PLAUSIBLE")
        kept = dict(f)
        # Evidence-or-silence: a CONFIRMED stamps CONFIRMED only WITH a non-empty executed
        # receipt; a receiptless CONFIRMED is an unproven claim → downgrade to PLAUSIBLE.
        evidence = v.get("evidence") if isinstance(v, dict) else None
        has_evidence = isinstance(evidence, str) and bool(evidence.strip())
        if verdict == "CONFIRMED" and has_evidence:
            kept["verdict"] = "CONFIRMED"
            kept["evidence"] = evidence
        else:
            kept["verdict"] = "PLAUSIBLE"
        kept["severity"] = _kept_severity(f, v, honored)
        survivors.append(kept)
        from_severity = f.get("severity")
        if circuit_breaker.is_blocking(from_severity) and not circuit_breaker.is_blocking(kept["severity"]):
            entry = {
                "id": fid,
                "file": f.get("file"),
                "title": f.get("title"),
                "from": from_severity,
                "to": kept["severity"],
            }
            if isinstance(reason, str) and reason.strip():
                entry["reason"] = reason.strip()
            downgrades.append(entry)
    unmatched = [vid for vid in by_id if vid not in matched_ids]
    return {
        "findings": survivors,
        "drops": drops,
        "downgrades": downgrades,
        "unmatched": unmatched,
        "unverified": unverified,
        "ambiguous": sorted(ambiguous_ids),
    }


def _severity_rank(severity):
    # Fail-closed / never-raise: a non-str severity (a model may emit a list/dict) is
    # unhashable, so guard BEFORE the dict lookup — treat it as the unknown rank (99) rather
    # than letting `_SEV_RANK.get(<unhashable>, 99)` raise TypeError and blow up the fold.
    if not isinstance(severity, str):
        return 99
    return _SEV_RANK.get(severity, 99)


def _rank_key(f):
    file = f.get("file") if isinstance(f, dict) else ""
    if not isinstance(file, str):
        file = ""
    line = f.get("line") if isinstance(f, dict) else 0
    try:
        line_val = int(line) if line is not None else 0
    except (TypeError, ValueError):
        line_val = 0
    sev = f.get("severity") if isinstance(f, dict) else None
    return (_severity_rank(sev), file == "", file, line_val)


def _union_dimensions(members):
    parts = []
    seen = set()
    for m in members:
        dim = m.get("dimension")
        if isinstance(dim, list):
            normalized = panel_tally.normalize_dimension(dim)
            if not normalized:
                continue
            for p in normalized.split(" + "):
                if p and p not in seen:
                    seen.add(p)
                    parts.append(p)
        elif isinstance(dim, str) and dim and dim not in seen:
            seen.add(dim)
            parts.append(dim)
    return " + ".join(parts)


def _eff_sev(severity):
    """Effective severity: a valid tier passes through unchanged; any non-tier value
    (malformed / off-scale / unhashable list-or-dict) coerces to the fail-closed blocking
    default. `x in _TIERS` compares element-wise, so an unhashable severity never raises.
    Used by the merge fold so both the merged severity and the confirming-member comparison
    are deterministic regardless of member order (identity on a valid tier)."""
    return severity if severity in _TIERS else _DEFAULT_BLOCKING_SEVERITY


def _merge_group(members):
    if not members:
        return {}
    rep = max(members, key=lambda m: (-_severity_rank(m.get("severity")), members.index(m)))
    merged = dict(rep)
    bodies = []
    for m in members:
        body = m.get("body")
        if isinstance(body, str) and body.strip():
            bodies.append(body.strip())
    if bodies:
        merged["body"] = _BODY_SEP.join(bodies)
    # G1: use the EFFECTIVE severity (a valid tier, or the fail-closed blocking default for
    # any non-tier value) so both the merged severity and the confirming-member comparison
    # are DETERMINISTIC regardless of member order. `_eff_sev` is identity on a valid tier,
    # so valid-tier behavior is unchanged; for malformed input the merged severity is always
    # a valid tier and the confirming test no longer depends on the rep's input position.
    max_sev = _eff_sev(rep.get("severity"))   # the merged (highest) severity — always a valid tier
    merged["severity"] = max_sev
    # F2 / A4b: the merged verdict is ORDER-INDEPENDENT and provenance-correct — GATE-
    # eligibility must not depend on model-supplied member order. The merge is CONFIRMED iff
    # some member AT THE MERGED (highest) effective severity is CONFIRMED with a non-empty
    # executed receipt; it carries that member's evidence (the first such member in input
    # order, so the carry is deterministic). A lower-severity CONFIRMED never promotes (no
    # receipt is fabricated onto the higher-severity finding); otherwise the merge is
    # PLAUSIBLE and any inherited `evidence` (carried by `dict(rep)`) is dropped. Both sides
    # of the `==` are `_eff_sev`-coerced valid tiers, so an unhashable severity never raises.
    confirming = None
    for m in members:
        ev = m.get("evidence")
        if (_eff_sev(m.get("severity")) == max_sev and m.get("verdict") == "CONFIRMED"
                and isinstance(ev, str) and ev.strip()):
            confirming = m
            break
    if confirming is not None:
        merged["verdict"] = "CONFIRMED"
        merged["evidence"] = confirming.get("evidence")
    else:
        merged["verdict"] = "PLAUSIBLE"
        merged.pop("evidence", None)
    dims = _union_dimensions(members)
    if dims:
        merged["dimension"] = dims
    return merged


def _valid_grouping(survivors, grouping):
    if grouping is None or not isinstance(grouping, list):
        return None
    survivor_ids = [s["id"] for s in survivors if isinstance(s, dict) and isinstance(s.get("id"), str)]
    expected = set(survivor_ids)
    if len(survivor_ids) != len(expected):
        return None
    seen = []
    groups = []
    for g in grouping:
        if not isinstance(g, dict):
            return None
        member_ids = g.get("member_ids")
        # An empty member_ids is invalid (nothing to merge; `max` over no members would
        # raise): reject the whole grouping so it fails open to unmerged survivors (A1).
        if not isinstance(member_ids, list) or not member_ids:
            return None
        for mid in member_ids:
            if not isinstance(mid, str) or mid not in expected:
                return None
            seen.append(mid)
        groups.append({
            "group_id": g.get("group_id"),
            "member_ids": list(member_ids),
        })
    if set(seen) != expected or len(seen) != len(expected):
        return None
    return groups


def merge_and_rank(survivors, grouping=None):
    """Finalize verified survivors: merge same-root-cause groups and rank — dropping nothing.

    Coverage: every id-bearing survivor's staged id appears exactly once; no dict survivor
    is ever dropped.
    """
    if not isinstance(survivors, list):
        survivors = []
    valid = [s for s in survivors if isinstance(s, dict) and isinstance(s.get("id"), str)]
    idless = [s for s in survivors if isinstance(s, dict) and not isinstance(s.get("id"), str)]
    by_id = {s["id"]: s for s in valid}
    groups = _valid_grouping(valid, grouping)
    findings = []
    merges = []
    if groups is None:
        findings = [dict(s) for s in valid]
    else:
        grouped_ids = set()
        for g in groups:
            members = [by_id[mid] for mid in g["member_ids"]]
            merged = _merge_group(members)
            rep = max(members, key=lambda m: (-_severity_rank(m.get("severity")), members.index(m)))
            kept_id = rep.get("id")
            merged["id"] = kept_id
            findings.append(merged)
            merges.append({
                "group_id": g["group_id"],
                "member_ids": list(g["member_ids"]),
                "kept_id": kept_id,
            })
            grouped_ids.update(g["member_ids"])
        for s in valid:
            if s["id"] not in grouped_ids:
                findings.append(dict(s))
    findings.extend(dict(s) for s in idless)
    findings.sort(key=_rank_key)
    return {"findings": findings, "merges": merges}
