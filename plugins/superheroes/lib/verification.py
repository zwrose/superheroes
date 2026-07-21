#!/usr/bin/env python3
"""Deterministic consumer of the per-finding verification stage (#506).

Sibling of loop_synthesis.py: applies a review panel's per-finding verification verdicts
(CONFIRMED / PLAUSIBLE / REFUTED) deterministically so accounting stays reproducible even
though a model made the judgments. stdlib only; never raises on bad input; fail-closed —
a model's silence or malformed verdict never drops a finding.
"""
import circuit_breaker

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


def _kept_severity(f, v):
    verdict_severity = v.get("severity") if isinstance(v, dict) else None
    if verdict_severity in _TIERS:
        return verdict_severity
    finding_severity = f.get("severity")
    if finding_severity in _TIERS:
        return finding_severity
    return _DEFAULT_BLOCKING_SEVERITY


def apply_verdicts(findings, verdicts):
    """Consume per-finding verification verdicts; fail-closed on ambiguity."""
    by_id = {}
    if isinstance(verdicts, list):
        for v in verdicts:
            if isinstance(v, dict) and isinstance(v.get("id"), str):
                by_id[v["id"]] = v
    if not isinstance(findings, list):
        findings = []
    matched_ids = set()
    survivors, drops, downgrades = [], [], []
    for f in findings:
        if not isinstance(f, dict):
            continue
        fid = f.get("id")
        if not isinstance(fid, str):
            fid = None
        v = by_id.get(fid) if fid is not None else None
        if v is not None and fid is not None:
            matched_ids.add(fid)
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
        kept = dict(f)
        if verdict == "CONFIRMED":
            kept["verdict"] = "CONFIRMED"
            if isinstance(v, dict) and v.get("evidence") is not None:
                kept["evidence"] = v["evidence"]
        else:
            kept["verdict"] = "PLAUSIBLE"
        kept["severity"] = _kept_severity(f, v)
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
    return {"findings": survivors, "drops": drops, "downgrades": downgrades, "unmatched": unmatched}


def _severity_rank(severity):
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
    dims = []
    seen = set()
    for m in members:
        dim = m.get("dimension")
        if isinstance(dim, list):
            for d in dim:
                if d not in seen:
                    seen.add(d)
                    dims.append(d)
        elif isinstance(dim, str) and dim and dim not in seen:
            seen.add(dim)
            dims.append(dim)
    return dims


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
    merged["severity"] = rep.get("severity")
    merged["verdict"] = "CONFIRMED" if any(m.get("verdict") == "CONFIRMED" for m in members) else "PLAUSIBLE"
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
        if not isinstance(member_ids, list):
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
