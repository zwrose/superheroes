#!/usr/bin/env python3
# plugins/superheroes/lib/guardian_sweep.py
"""Guardian sweep pipeline: collect (side-effect-free) + finalize (transactional).

Stdlib-only. Deterministic shell for repo-health sweeps — never edits code or files issues.
"""
import argparse
import json
import os
import re
import subprocess
import sys

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import core_md          # noqa: E402
import file_lock        # noqa: E402
import guardian_lens    # noqa: E402
import guardian_report  # noqa: E402
import guardian_store   # noqa: E402
import store_core       # noqa: E402

_CONFIG_BLOCK = re.compile(
    r"```json\s+guardian-config\s*\n(.*?)\n```", re.DOTALL)

_VERIFY_TIMEOUT = 30


def _repo_root(cwd):
    out = store_core.run_git(cwd, "rev-parse", "--show-toplevel")
    return os.path.realpath(out) if out else os.path.realpath(cwd)


def read_config(cwd, root=None):
    """Read guardian.md layer → {thresholds, coverage}. Empty/absent → defaults."""
    layer_p = guardian_store.guardian_layer_path(cwd, root)
    thresholds = dict(guardian_lens.RED_LINE_THRESHOLDS)
    coverage = []
    if core_md._layer_is_empty(layer_p):
        return {"thresholds": thresholds, "coverage": coverage}
    try:
        with open(layer_p, encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return {"thresholds": thresholds, "coverage": coverage}
    m = _CONFIG_BLOCK.search(text)
    if not m:
        return {"thresholds": thresholds, "coverage": coverage}
    try:
        block = json.loads(m.group(1))
    except ValueError:
        return {"thresholds": thresholds, "coverage": coverage}
    if not isinstance(block, dict):
        return {"thresholds": thresholds, "coverage": coverage}
    if isinstance(block.get("thresholds"), dict):
        thresholds.update(block["thresholds"])
    cov = block.get("coverage")
    if isinstance(cov, list):
        coverage = cov
    return {"thresholds": thresholds, "coverage": coverage}


def _manifest_tags(repo):
    """Map repo-root manifests to stack tags they back."""
    tags = set()
    if os.path.isfile(os.path.join(repo, "package.json")):
        tags.update(("node", "js", "ts"))
    if os.path.isfile(os.path.join(repo, "pyproject.toml")) or os.path.isfile(
            os.path.join(repo, "requirements.txt")):
        tags.add("python")
    if os.path.isfile(os.path.join(repo, "Cargo.toml")):
        tags.add("rust")
    if os.path.isfile(os.path.join(repo, "go.mod")):
        tags.add("go")
    return tags


def _config_paths(config):
    """Repo-relative paths declared in coverage config entries."""
    paths = []
    for entry in config.get("coverage") or []:
        if isinstance(entry, dict) and isinstance(entry.get("path"), str):
            paths.append(entry["path"])
    return paths


def verify_config(cwd, root=None, run=None, config=None, needed_facts=None):
    """Trust-but-verify the four FACTS. `run` is injectable for tests."""
    run = run or subprocess.run
    config = config if config is not None else read_config(cwd, root)
    repo = _repo_root(cwd)
    facts = []
    needed = needed_facts if needed_facts is not None else set()

    # 1. verify-command — only probe when a lens actually depends on it
    core = core_md.read(cwd, root)
    if "verify-command" not in needed:
        facts.append({
            "fact": "verify-command",
            "status": "not-run",
            "receipt": "no lens depends on verify-command",
        })
    else:
        vcmd = (core or {}).get("verifyCommand")
        if not vcmd:
            facts.append({
                "fact": "verify-command",
                "status": "absent",
                "receipt": "no verifyCommand in core.md",
            })
        else:
            try:
                r = run(vcmd, shell=True, cwd=cwd, capture_output=True, text=True,
                        timeout=_VERIFY_TIMEOUT)
                if r.returncode == 0:
                    status, receipt = "ok", "%s → exit 0" % vcmd
                else:
                    status, receipt = "failed", "%s → exit %d" % (vcmd, r.returncode)
            except subprocess.TimeoutExpired:
                status, receipt = "not-collected", "%s → timeout" % vcmd
            except (OSError, subprocess.SubprocessError) as exc:
                status, receipt = "not-collected", "%s → %s" % (vcmd, exc)

            facts.append({"fact": "verify-command", "status": status, "receipt": receipt})

    # 2. recorded-coverage
    cov = config.get("coverage") or []
    if cov:
        facts.append({
            "fact": "recorded-coverage",
            "status": "present",
            "receipt": cov,
        })
    else:
        facts.append({
            "fact": "recorded-coverage",
            "status": "absent",
            "receipt": "none recorded",
        })

    # 3. stack-tags
    tags = list((core or {}).get("stackTags") or [])
    if not tags:
        facts.append({
            "fact": "stack-tags",
            "status": "absent",
            "receipt": "no stackTags in core.md",
        })
    else:
        backed = _manifest_tags(repo)
        matched, mismatched = [], []
        for t in tags:
            if t in backed:
                matched.append(t)
            else:
                mismatched.append(t)
        if mismatched:
            status = "mismatch"
            receipt = {"matched": matched, "mismatched": mismatched}
        else:
            status = "match"
            receipt = {"matched": matched, "mismatched": []}
        facts.append({"fact": "stack-tags", "status": status, "receipt": receipt})

    # 4. paths
    paths = _config_paths(config)
    if not paths:
        facts.append({
            "fact": "paths",
            "status": "absent",
            "receipt": "no paths in config",
        })
    else:
        dangling = [p for p in paths if not os.path.isfile(os.path.join(repo, p))]
        if dangling:
            facts.append({
                "fact": "paths",
                "status": "dangling",
                "receipt": {"checked": paths, "dangling": dangling},
            })
        else:
            facts.append({
                "fact": "paths",
                "status": "ok",
                "receipt": {"checked": paths, "dangling": []},
            })

    return {"facts": facts}


_FACT_SATISFIED = {
    "verify-command": "ok",
    "recorded-coverage": "present",
    "stack-tags": "match",
    "paths": "ok",
}


def _unsatisfied_facts(fact_verdicts):
    statuses = {f["fact"]: f["status"] for f in fact_verdicts}
    return {
        fact for fact, satisfied in _FACT_SATISFIED.items()
        if statuses.get(fact) != satisfied
    }


def _is_filed_open(rec):
    """A filed disposition with an open issue reference."""
    return rec.get("disposition") == "filed" and rec.get("issue")


def _is_trade_disposition(rec):
    return rec.get("disposition") in ("accepted", "declined")


def _materially_worsened(candidate, rec):
    """Best-effort: compare candidate metric against ledger metricAtDisposition."""
    metric_at = rec.get("metricAtDisposition")
    if metric_at is None:
        return False
    cur = candidate.get("metric")
    if cur is None:
        return False
    try:
        return float(cur) > float(metric_at)
    except (TypeError, ValueError):
        return False


def _filter_red_lines(red_lines):
    """Drop red-line entries whose kind is not in RED_LINE_KINDS."""
    allowed = set(guardian_lens.RED_LINE_KINDS)
    return [r for r in red_lines if r.get("kind") in allowed]


def collect(cwd, lenses=None, root=None, run=None, config=None):
    """Side-effect-free collection. MUST NOT write latest.json."""
    lenses = lenses if lenses is not None else guardian_lens.registered_lenses()
    config = config if config is not None else read_config(cwd, root)
    needed_facts = set()
    for lens in lenses:
        needed_facts.update(lens.required_facts)
    facts = verify_config(cwd, root, run=run, config=config, needed_facts=needed_facts)
    unsatisfied = _unsatisfied_facts(facts["facts"])

    prev = guardian_store.read_snapshot(cwd, root)
    prev_identity = guardian_store.snapshot_identity(prev)
    prev_lenses = (prev or {}).get("lenses", {})

    surfaced = []
    red_lines = []
    ledger_status = []
    funnel_raised = {}
    killed_by_drift = []
    killed_by_ledger = []
    degraded_lenses = []
    malformed = []
    lens_meta = {}
    next_lenses = {}

    ledger = guardian_store.read_ledger(cwd, root)
    suppress_via_ledger = ledger["status"] in ("ok", "absent")

    for lens in lenses:
        if set(lens.required_facts) & unsatisfied:
            reason = "required facts unsatisfied: %s" % (
                ", ".join(sorted(set(lens.required_facts) & unsatisfied)))
            degraded_lenses.append(lens.degrade(reason))
            continue

        ctx = {"cwd": cwd, "root": root, "config": config, "run": run}
        out = lens.collect(ctx)
        candidates = out.get("candidates") or []
        cur_digest = out.get("digest")
        funnel_raised[lens.name] = len(candidates)

        cand_by_id = {}
        for i, c in enumerate(candidates):
            if isinstance(c, dict) and c.get("id"):
                cand_by_id[c["id"]] = c
            else:
                malformed.append({"lens": lens.name, "index": i, "repr": repr(c)})

        valid_candidates = list(cand_by_id.values())
        prev_entry = prev_lenses.get(lens.name)
        lens_new = (
            lens.name not in prev_lenses
            or prev_entry.get("collectorVersion") != lens.collector_version
        )
        if lens_new:
            d = {"new": [], "worsened": [], "resolved": []}
            drift_ids = []
        else:
            prev_digest = prev_entry.get("digest")
            d = lens.diff(prev_digest, cur_digest)
            drift_ids = list(d.get("new", [])) + list(d.get("worsened", []))

        rl = _filter_red_lines(lens.red_lines(valid_candidates))
        red_line_ids = {r["id"] for r in rl}
        red_lines.extend(rl)

        would_surface = set(drift_ids) | red_line_ids
        lens_surfaced = False

        for cid, cand in cand_by_id.items():
            if cid not in would_surface:
                killed_by_drift.append({
                    "id": cid,
                    "lens": lens.name,
                    "reason": "quiet-baseline" if lens_new else "no-drift",
                })

        for cid in sorted(would_surface):
            cand = cand_by_id.get(cid, {"id": cid})
            is_red = cid in red_line_ids
            if cid in drift_ids and cid in red_line_ids:
                drift_reason = "red-line"
            elif is_red:
                drift_reason = "red-line"
            elif cid in (d.get("new", []) if not lens_new else []):
                drift_reason = "new"
            else:
                drift_reason = "worsened" if cid in drift_ids else "red-line"

            if suppress_via_ledger and cid in ledger["byId"]:
                rec = ledger["byId"][cid]
                if _is_filed_open(rec) and not is_red:
                    issue = rec.get("issue", "")
                    ledger_status.append({
                        "id": cid,
                        "lens": lens.name,
                        "line": "filed as %s, verification pending" % issue,
                    })
                    continue
                if _is_trade_disposition(rec) and not is_red:
                    if _materially_worsened(cand, rec):
                        pass  # surface — materially worsened
                    else:
                        killed_by_ledger.append({
                            "id": cid,
                            "lens": lens.name,
                            "disposition": rec.get("disposition"),
                        })
                        continue

            entry = dict(cand)
            entry["lens"] = lens.name
            entry["driftReason"] = drift_reason
            surfaced.append(entry)
            lens_surfaced = True

        if lens_surfaced:
            lens_meta[lens.name] = {
                "validationGuidance": lens.validation_guidance,
                "consequenceTemplate": lens.consequence_template,
                "cost": lens.cost,
            }

        next_lenses[lens.name] = {
            "collectorVersion": lens.collector_version,
            "digest": cur_digest,
        }

    for lens in lenses:
        if lens.name not in next_lenses and lens.name in prev_lenses:
            next_lenses[lens.name] = prev_lenses[lens.name]

    swept_sha = store_core.run_git(cwd, "rev-parse", "HEAD")
    next_snapshot = {
        "schemaVersion": guardian_store.SNAPSHOT_SCHEMA_VERSION,
        "sweptSha": swept_sha,
        "vitals": (prev or {}).get("vitals", {}),
        "lenses": next_lenses,
    }
    assert set(next_snapshot) == set(guardian_store.SNAPSHOT_KEYS)

    return {
        "surfaced": surfaced,
        "funnel": {
            "raised": funnel_raised,
            "malformed": malformed,
            "killedByDrift": killed_by_drift,
            "killedByLedger": killed_by_ledger,
            "trackedFiled": list(ledger_status),
            "degradedLenses": degraded_lenses,
        },
        "lensMeta": lens_meta,
        "redLines": red_lines,
        "factVerdicts": facts["facts"],
        "ledgerStatus": ledger_status,
        "ledgerState": ledger["status"],
        "vitalsDelta": {},
        "nextSnapshot": next_snapshot,
        "prevIdentity": prev_identity,
        "sweptSha": swept_sha,
    }


def validate_dispositions(bundle, dispositions):
    """Total check: exactly one disposition per surfaced id."""
    errors = []
    surfaced_ids = [s["id"] for s in bundle.get("surfaced", [])]
    expected = set(surfaced_ids)
    seen = []
    for d in dispositions or []:
        if not isinstance(d, dict):
            errors.append("disposition entry is not an object")
            continue
        did = d.get("id")
        seen.append(did)
        verdict = d.get("verdict")
        if verdict not in ("validated", "rejected", "degraded"):
            errors.append("%s: verdict must be validated|rejected|degraded" % did)
        if verdict == "validated":
            for field in ("consequence", "receipt", "effort", "ledgerJoin"):
                val = d.get(field)
                if not isinstance(val, str) or not val:
                    errors.append("%s: validated requires non-empty %s" % (did, field))

    seen_set = set(seen)
    for sid in expected:
        if seen.count(sid) != 1:
            errors.append("surfaced id %s: expected exactly one disposition, got %d"
                          % (sid, seen.count(sid)))
    for did in seen_set - expected:
        errors.append("extra disposition for non-surfaced id %s" % did)

    return (len(errors) == 0, errors)


def finalize(cwd, bundle, dispositions, root=None):
    """Transactional finalize: validate → report first → baseline last, under sweep lock."""
    ok, errors = validate_dispositions(bundle, dispositions)
    if not ok:
        return {"ok": False, "reason": "invalid-dispositions", "errors": errors}

    lock_path = guardian_store.sweep_lock_path(cwd, root)
    try:
        file_lock.acquire(lock_path)
    except file_lock.LockHeld as exc:
        return {"ok": False, "reason": "raced", "lockHeld": exc.holder}

    try:
        current = guardian_store.read_snapshot(cwd, root)
        on_disk = guardian_store.snapshot_identity(current)
        if on_disk != bundle["prevIdentity"]:
            return {
                "ok": False,
                "reason": "raced",
                "onDisk": on_disk,
                "expected": bundle["prevIdentity"],
            }

        ledger = guardian_store.read_ledger(cwd, root)
        report_md = guardian_report.render(bundle, dispositions, ledger)

        rp = guardian_store.report_path(cwd, root)
        store_core.atomic_write(rp, report_md)

        snap_path = guardian_store.snapshot_path(cwd, root)
        store_core.atomic_write(
            snap_path, json.dumps(bundle["nextSnapshot"], indent=2) + "\n")

        return {
            "ok": True,
            "reportPath": rp,
            "snapshotPath": snap_path,
        }
    finally:
        file_lock.release(lock_path)


def main(argv=None):
    ap = argparse.ArgumentParser(description="guardian sweep pipeline")
    sub = ap.add_subparsers(dest="cmd", required=True)

    cp = sub.add_parser("collect")
    cp.add_argument("--cwd", default=".")
    cp.add_argument("--root", default=None)

    fp = sub.add_parser("finalize")
    fp.add_argument("--cwd", default=".")
    fp.add_argument("--root", default=None)
    fp.add_argument("--bundle", required=True)
    fp.add_argument("--dispositions", required=True)

    vp = sub.add_parser("verify-config")
    vp.add_argument("--cwd", default=".")
    vp.add_argument("--root", default=None)

    args = ap.parse_args(argv)
    try:
        if args.cmd == "collect":
            out = collect(args.cwd, root=args.root)
        elif args.cmd == "finalize":
            with open(args.bundle, encoding="utf-8") as fh:
                bundle = json.load(fh)
            with open(args.dispositions, encoding="utf-8") as fh:
                dispositions = json.load(fh)
            out = finalize(args.cwd, bundle, dispositions, root=args.root)
        else:
            # Standalone CLI has no lenses — skip spawning the verify command.
            out = verify_config(args.cwd, root=args.root, needed_facts=set())
    except Exception as exc:
        out = {"error": str(exc)}
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
