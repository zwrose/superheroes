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
import time

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import core_md          # noqa: E402
import file_lock        # noqa: E402
import guardian_ledger  # noqa: E402
import guardian_lens    # noqa: E402
import guardian_report  # noqa: E402
import guardian_store   # noqa: E402
import guardian_vitals  # noqa: E402
import mode_registry    # noqa: E402
import store_core       # noqa: E402

_CONFIG_BLOCK = re.compile(
    r"```json\s+guardian-config\s*\n(.*?)\n```", re.DOTALL)

CADENCE_DEFAULTS = {"minMerges": 10, "minDays": 14}

# Default verify / vitals time budget. This repo's lib suite measures ~125s and
# §3.7's worked example is 62s; 30s (the prior hard cap) made suite vitals
# permanently "not collected" on the repos the design cites. 300s clears both
# with headroom while still bounding a runaway suite.
_DEFAULT_VERIFY_BUDGET_SECONDS = 300
_VERIFY_STDOUT_CAP = 8 * 1024
# Aggregate budget across all filed-issue `gh issue view` lookups in one collect.
# Per-call timeout is capped so one hung call cannot consume the whole budget alone.
_ISSUE_RESOLVE_BUDGET_SECONDS = 30.0
_ISSUE_RESOLVE_PER_CALL_TIMEOUT = 10.0


def _repo_root(cwd):
    out = store_core.run_git(cwd, "rev-parse", "--show-toplevel")
    return os.path.realpath(out) if out else os.path.realpath(cwd)


def _positive_cadence_int(value):
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _resolve_cadence(raw):
    """Merge owner cadence over CADENCE_DEFAULTS; record positively-tuned keys."""
    cadence = dict(CADENCE_DEFAULTS)
    cadence_tuned = {}
    if not isinstance(raw, dict):
        return cadence, cadence_tuned
    for key in CADENCE_DEFAULTS:
        val = raw.get(key)
        if _positive_cadence_int(val):
            cadence[key] = val
            cadence_tuned[key] = True
    return cadence, cadence_tuned


def read_config(cwd, root=None):
    """Read guardian.md layer → thresholds, coverage, vitals knobs.

    Empty/absent → defaults with `configStatus` healthy (defaults are authoritative).
    Unreadable / malformed / non-object config → defaults with `configStatus` degraded
    (benching authority revoked; the degradation is visible to report_card).
    Vitals collection is on by default; a guardian-config `vitals: false` (or
    `collectVitals: false`) disables it. `verifyBudgetSeconds` (alias
    `vitalsBudgetSeconds`) tunes the shared verify/vitals time budget."""
    layer_p = guardian_store.guardian_layer_path(cwd, root)
    thresholds = dict(guardian_lens.RED_LINE_THRESHOLDS)
    coverage = []
    vitals_enabled = True
    verify_budget = _DEFAULT_VERIFY_BUDGET_SECONDS
    report_card = None
    cadence, cadence_tuned = _resolve_cadence(None)

    def _result(status, *, report_card_value=None, notes=None):
        return {
            "thresholds": thresholds,
            "coverage": coverage,
            "vitalsEnabled": vitals_enabled,
            "verifyBudgetSeconds": verify_budget,
            "reportCard": report_card_value,
            "cadence": cadence,
            "cadenceTuned": cadence_tuned,
            "configStatus": status,
            "configNotes": list(notes or []),
        }

    if core_md._layer_is_empty(layer_p):
        return _result("healthy")
    try:
        with open(layer_p, encoding="utf-8") as fh:
            text = fh.read()
    except OSError as exc:
        return _result(
            "degraded",
            notes=["guardian-config unreadable (%s)" % type(exc).__name__])
    m = _CONFIG_BLOCK.search(text)
    if not m:
        # Layer present but no config fence — defaults authoritative (healthy).
        return _result("healthy")
    try:
        block = json.loads(m.group(1))
    except ValueError:
        return _result(
            "degraded",
            notes=["guardian-config JSON is malformed"])
    if not isinstance(block, dict):
        return _result(
            "degraded",
            notes=["guardian-config block is not an object (got %s)"
                   % type(block).__name__])
    if isinstance(block.get("thresholds"), dict):
        thresholds.update(block["thresholds"])
    cov = block.get("coverage")
    if isinstance(cov, list):
        coverage = cov
    if block.get("vitals") is False or block.get("collectVitals") is False:
        vitals_enabled = False
    budget = block.get("verifyBudgetSeconds")
    if budget is None:
        budget = block.get("vitalsBudgetSeconds")
    if isinstance(budget, (int, float)) and not isinstance(budget, bool) and budget > 0:
        verify_budget = float(budget)
    notes = []
    if "reportCard" in block and not isinstance(block.get("reportCard"), dict):
        notes.append("guardian-config reportCard is not an object")
        return _result("degraded", notes=notes)
    if isinstance(block.get("reportCard"), dict):
        report_card = block["reportCard"]
    cadence, cadence_tuned = _resolve_cadence(block.get("cadence"))
    return _result("healthy", report_card_value=report_card, notes=notes)


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


def _bound_stdout(text):
    if not isinstance(text, str):
        return ""
    if len(text) <= _VERIFY_STDOUT_CAP:
        return text
    return text[-_VERIFY_STDOUT_CAP:]


def verify_config(cwd, root=None, run=None, config=None, needed_facts=None):
    """Trust-but-verify the four FACTS. `run` is injectable for tests.

    When `verify-command` is needed, runs it once and returns bounded stdout +
    elapsed seconds alongside the fact verdict so vitals can share the same
    execution (never a second run)."""
    run = run or subprocess.run
    config = config if config is not None else read_config(cwd, root)
    budget = config.get("verifyBudgetSeconds", _DEFAULT_VERIFY_BUDGET_SECONDS)
    repo = _repo_root(cwd)
    facts = []
    needed = needed_facts if needed_facts is not None else set()
    verify_result = {
        "status": "not-run",
        "receipt": "no requester depends on verify-command",
        "stdout": "",
        "durationSeconds": None,
    }

    # 1. verify-command — only probe when a lens or vitals depends on it
    core = core_md.read(cwd, root)
    # Resolve the calibrated verify command from the SAME core.md read (no second read).
    # It is threaded onto each lens ctx below as ctx["verifyCommand"] so a tool-free lens
    # (the docs lens) can resolve the paths the command names without re-reading core.md or
    # spawning git. Whether a lens depends on the verify-command FACT (which RUNS the
    # command) is a separate question; this value is READ-only calibration.
    verify_command = (core or {}).get("verifyCommand")
    if "verify-command" not in needed:
        facts.append({
            "fact": "verify-command",
            "status": "not-run",
            "receipt": "no lens depends on verify-command",
        })
    else:
        vcmd = verify_command
        if not vcmd:
            verify_result = {
                "status": "absent",
                "receipt": "no verifyCommand in core.md",
                "stdout": "",
                "durationSeconds": None,
            }
            facts.append({
                "fact": "verify-command",
                "status": "absent",
                "receipt": "no verifyCommand in core.md",
            })
        else:
            stdout = ""
            duration = None
            try:
                t0 = time.monotonic()
                r = run(vcmd, shell=True, cwd=cwd, capture_output=True, text=True,
                        timeout=budget)
                duration = time.monotonic() - t0
                stdout = _bound_stdout(getattr(r, "stdout", None) or "")
                if r.returncode == 0:
                    status, receipt = "ok", "%s → exit 0" % vcmd
                else:
                    status, receipt = "failed", "%s → exit %d" % (vcmd, r.returncode)
            except subprocess.TimeoutExpired as exc:
                duration = budget
                stdout = _bound_stdout(
                    (getattr(exc, "stdout", None) or "")
                    if isinstance(getattr(exc, "stdout", None), str)
                    else "")
                status, receipt = "not-collected", "%s → timeout" % vcmd
            except (OSError, subprocess.SubprocessError) as exc:
                status, receipt = "not-collected", "%s → %s" % (vcmd, exc)

            verify_result = {
                "status": status,
                "receipt": receipt,
                "stdout": stdout,
                "durationSeconds": duration,
            }
            # Trust boundary: raw verify stdout stays local to verify_result for the
            # vitals parser. Never leak it into factVerdicts / the model-facing bundle.
            facts.append({
                "fact": "verify-command",
                "status": status,
                "receipt": receipt,
                "durationSeconds": duration,
            })

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

    return {"facts": facts, "verifyResult": verify_result,
            "verifyCommand": verify_command}


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


def _is_settled_non_trade(rec):
    """Terminal settled dispositions that are never re-derived (ordinary drift)."""
    return rec.get("disposition") == "triaged-out"


_ISSUE_NUM_RE = re.compile(r"#?(\d+)")
_ISSUE_TERMINAL = frozenset(("closed", "merged"))


def _resolve_issue_state(issue_ref, *, cwd, deadline=None, cache=None):
    """Best-effort linked-issue state → 'open'|'closed'|'merged'|None.

    None means unverifiable (no ref, unparseable, gh missing/failed, or aggregate
    resolve budget exhausted). Callers must fail closed: do not run
    verified-fixed/reopened until a terminal state is confirmed.
    Uses subprocess.run directly — not the sweep's injectable `run`, which stubs the
    verify shell command in tests. Distinct issue numbers are cached; the aggregate
    `deadline` bounds total blocked time across all lookups in one collect."""
    if not isinstance(issue_ref, str) or not issue_ref.strip():
        return None
    m = _ISSUE_NUM_RE.search(issue_ref.strip())
    if not m:
        return None
    num = m.group(1)
    if cache is not None and num in cache:
        return cache[num]
    if deadline is not None:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            if cache is not None:
                cache[num] = None
            return None
        timeout = min(_ISSUE_RESOLVE_PER_CALL_TIMEOUT, remaining)
    else:
        timeout = _ISSUE_RESOLVE_PER_CALL_TIMEOUT
    try:
        r = subprocess.run(
            ["gh", "issue", "view", num, "--json", "state"],
            cwd=cwd, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        if cache is not None:
            cache[num] = None
        return None
    if r.returncode != 0:
        if cache is not None:
            cache[num] = None
        return None
    try:
        data = json.loads(r.stdout)
    except ValueError:
        if cache is not None:
            cache[num] = None
        return None
    if not isinstance(data, dict):
        if cache is not None:
            cache[num] = None
        return None
    state = data.get("state")
    if not isinstance(state, str):
        if cache is not None:
            cache[num] = None
        return None
    state = state.strip().lower()
    if state in ("open", "closed", "merged"):
        if cache is not None:
            cache[num] = state
        return state
    if cache is not None:
        cache[num] = None
    return None


def _issue_ready_for_closure(issue_state):
    """True only when the linked issue is confirmed merged or closed."""
    return issue_state in _ISSUE_TERMINAL


def _filter_red_lines(red_lines):
    """Drop red-line entries whose kind is not in RED_LINE_KINDS."""
    allowed = set(guardian_lens.RED_LINE_KINDS)
    return [r for r in red_lines if r.get("kind") in allowed]


def _storage_mode(cwd, root=None):
    try:
        return mode_registry.resolve(cwd, root)["mode"]
    except Exception:
        return mode_registry.IN_REPO


def _guardian_committed(cwd, root, storage_mode):
    """Whether in-repo guardian artifacts are clean in the working tree."""
    if storage_mode == mode_registry.GLOBAL:
        return "machine-local"
    gdir = guardian_store.guardian_dir(cwd, root)
    rel = os.path.relpath(gdir, _repo_root(cwd))
    porcelain = store_core.run_git(cwd, "status", "--porcelain", "--", rel)
    if porcelain is None:
        return "unknown"
    if porcelain.strip():
        return "uncommitted"
    # Untracked-but-absent dir (no artifacts yet) is still "uncommitted" until a PR.
    tracked = store_core.run_git(cwd, "ls-files", "--", rel)
    if not (tracked or "").strip():
        return "uncommitted"
    return "committed"


def collect(cwd, lenses=None, root=None, run=None, config=None):
    """Side-effect-free collection. MUST NOT write latest.json."""
    lenses = lenses if lenses is not None else guardian_lens.registered_lenses()
    config = config if config is not None else read_config(cwd, root)
    needed_facts = set()
    for lens in lenses:
        needed_facts.update(lens.required_facts)
    if config.get("vitalsEnabled", True):
        needed_facts.add("verify-command")
    facts = verify_config(cwd, root, run=run, config=config, needed_facts=needed_facts)
    unsatisfied = _unsatisfied_facts(facts["facts"])
    # Calibrated verify command, resolved once above — threaded onto each lens ctx so a
    # tool-free lens (docs) resolves the paths it names without re-reading core.md.
    verify_command = facts.get("verifyCommand")

    prev = guardian_store.read_snapshot(cwd, root)
    prev_identity = guardian_store.snapshot_identity(prev)
    prev_lenses = (prev or {}).get("lenses", {})

    surfaced = []
    red_lines = []
    ledger_status = []
    funnel_raised = {}
    killed_by_drift = []
    killed_by_ledger = []
    killed_by_bench = []
    match_notes = []
    degraded_lenses = []
    malformed = []
    lens_meta = {}
    next_lenses = {}
    filed_observations = {}
    lens_results = {}

    ledger = guardian_store.read_ledger(cwd, root)
    # partial disables ledger suppression: read_ledger drops invalid bodies from
    # byId, which would otherwise make a normalized collision look unique and
    # defeat fail-open. unreadable/malformed/newer never suppress. Benching
    # requires a fully ok ledger AND a healthy guardian-config.
    suppress_via_ledger = ledger["status"] in ("ok", "absent")
    report_card_notes = []
    config_status = config.get("configStatus") or "healthy"
    if config_status == "degraded":
        report_card_notes.extend(config.get("configNotes") or [])
    card = guardian_ledger.report_card(
        ledger["records"], overrides=config.get("reportCard"),
        notes_out=report_card_notes, config_status=config_status)
    if ledger["status"] not in ("ok", "absent"):
        # Duplicate / invalid / partially-read ledger: no benching authority this sweep.
        for name, entry in card.items():
            if entry.get("benched"):
                entry["benched"] = False
                entry["reason"] = (
                    "%s has no benching authority this sweep: ledger status is %s"
                    % (name, ledger["status"]))
        if ledger.get("note"):
            report_card_notes.append(ledger["note"])
    benched_lenses = {name for name, entry in card.items() if entry.get("benched")}
    issue_deadline = time.monotonic() + _ISSUE_RESOLVE_BUDGET_SECONDS
    issue_cache = {}

    for lens in lenses:
        if set(lens.required_facts) & unsatisfied:
            reason = "required facts unsatisfied: %s" % (
                ", ".join(sorted(set(lens.required_facts) & unsatisfied)))
            degraded_lenses.append(lens.degrade(reason))
            continue

        prev_entry = prev_lenses.get(lens.name)
        lens_new = (
            lens.name not in prev_lenses
            or prev_entry.get("collectorVersion") != lens.collector_version
        )
        ctx = {
            "cwd": cwd,
            "root": root,
            "config": config,
            "run": run,
            "prevDigest": None if lens_new else prev_entry.get("digest"),
            "verifyCommand": verify_command,
        }
        try:
            out = lens.collect(ctx) or {}
            status, reason = guardian_lens.classify_collect(out)
            boundary = guardian_lens.permanent_boundary(out)
        except guardian_lens.MalformedCollect as exc:
            out, status, reason, boundary = {}, "not-collected", "malformed collect: %s" % exc, False
        except Exception as exc:
            out, status, reason, boundary = {}, "not-collected", "collect raised: %s" % exc, False

        if status == "not-collected":
            degraded_lenses.append(lens.degrade(reason))
            continue

        if status == "partial":
            degraded_lenses.append(lens.degrade(reason))

        candidates = out.get("candidates") or []
        cur_digest = out.get("digest")
        funnel_raised[lens.name] = len(candidates)
        lens_results[lens.name] = {
            "lens": lens,
            "status": status,
            "digest": cur_digest,
            "reason": reason,
            "fresh": True,
        }

        cand_by_id = {}
        for i, c in enumerate(candidates):
            if isinstance(c, dict) and c.get("id"):
                cid = c["id"]
                if cid in cand_by_id:
                    malformed.append({
                        "lens": lens.name,
                        "index": i,
                        "repr": repr(c),
                        "reason": "duplicate-id",
                    })
                else:
                    cand_by_id[cid] = c
            else:
                malformed.append({"lens": lens.name, "index": i, "repr": repr(c)})

        valid_candidates = list(cand_by_id.values())
        try:
            if lens_new:
                d = {"new": [], "worsened": [], "resolved": []}
                drift_ids = []
            else:
                d = lens.diff(ctx["prevDigest"], cur_digest)
                drift_ids = list(d.get("new", [])) + list(d.get("worsened", []))

            rl = _filter_red_lines(lens.red_lines(valid_candidates))
        except Exception as exc:
            funnel_raised.pop(lens.name, None)
            malformed[:] = [m for m in malformed if m.get("lens") != lens.name]
            degraded_lenses.append(lens.degrade("diff/red_lines raised: %s" % exc))
            continue

        red_line_ids = {r["id"] for r in rl}
        red_lines.extend(rl)

        would_surface = set(drift_ids) | red_line_ids
        lens_surfaced = False
        lens_is_benched = lens.name in benched_lenses

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

            rec, match_note = (None, None)
            ambiguous_match = False
            if suppress_via_ledger:
                rec, match_note = guardian_ledger.match(cid, ledger["byId"])
                if match_note:
                    match_notes.append({
                        "id": cid,
                        "lens": lens.name,
                        "note": match_note,
                    })
                    if "ambiguous" in match_note:
                        ambiguous_match = True
                        # Ambiguity revokes benching for this lens — fail open end to end.
                        if lens.name in benched_lenses:
                            benched_lenses.discard(lens.name)
                            lens_is_benched = False
                            if lens.name in card:
                                card[lens.name]["benched"] = False
                                card[lens.name]["reason"] = (
                                    "%s has no benching authority this sweep: "
                                    "normalized-identity collision (matcher fail-open)"
                                    % lens.name)

            if rec is not None:
                if _is_filed_open(rec) and not is_red:
                    issue = rec.get("issue", "")
                    ledger_status.append({
                        "id": cid,
                        "lens": lens.name,
                        "line": "filed as %s, verification pending" % issue,
                    })
                    continue
                if _is_settled_non_trade(rec) and not is_red:
                    killed_by_ledger.append({
                        "id": cid,
                        "lens": lens.name,
                        "disposition": rec.get("disposition"),
                    })
                    continue
                if _is_trade_disposition(rec) and not is_red:
                    if guardian_ledger.materially_worsened(cand, rec):
                        pass  # surface — materially worsened
                    else:
                        killed_by_ledger.append({
                            "id": cid,
                            "lens": lens.name,
                            "disposition": rec.get("disposition"),
                        })
                        continue

            # Benching suppresses ordinary drift only — never a red line, and never
            # after an ambiguous identity match (fail-open must reach the surface).
            if lens_is_benched and not is_red and not ambiguous_match:
                killed_by_bench.append({
                    "id": cid,
                    "lens": lens.name,
                    "reason": card[lens.name].get("reason") or "benched",
                })
                continue

            entry = dict(cand)
            entry["lens"] = lens.name
            entry["driftReason"] = drift_reason
            surfaced.append(entry)
            lens_surfaced = True

        # Filed-closure observations for every filed record of this lens.
        for lrec in ledger["records"]:
            if not isinstance(lrec, dict) or lrec.get("disposition") != "filed":
                continue
            rid = lrec.get("id")
            if not isinstance(rid, str) or guardian_ledger.lens_of(rid) != lens.name:
                continue
            matched_cand = cand_by_id.get(rid)
            if matched_cand is None:
                for cid, c in cand_by_id.items():
                    hit, _ = guardian_ledger.match(cid, {rid: lrec})
                    if hit is not None:
                        matched_cand = c
                        break
            filed_observations[rid] = {
                "present": matched_cand is not None,
                "candidate": matched_cand,
                "issue": lrec.get("issue"),
                "issueState": _resolve_issue_state(
                    lrec.get("issue"), cwd=cwd,
                    deadline=issue_deadline, cache=issue_cache),
            }

        if lens_surfaced:
            lens_meta[lens.name] = {
                "validationGuidance": lens.validation_guidance,
                "consequenceTemplate": lens.consequence_template,
                "cost": lens.cost,
            }

        # Transient partials still withhold baseline on version change; permanent-boundary
        # partials may seed a new collector version (structural limit, not transient failure).
        if status == "collected" or (
                status == "partial" and cur_digest is not None
                and (not lens_new or boundary)):
            next_lenses[lens.name] = {
                "collectorVersion": lens.collector_version,
                "digest": cur_digest,
            }

    for lens in lenses:
        if lens.name not in next_lenses and lens.name in prev_lenses:
            next_lenses[lens.name] = prev_lenses[lens.name]

    swept_sha = store_core.run_git(cwd, "rev-parse", "HEAD")
    sweep = guardian_ledger.make_sweep(swept_sha or "unknown")
    sweep_id = sweep["sweepId"]

    lens_digests = {
        name: entry.get("digest")
        for name, entry in next_lenses.items()
        if isinstance(entry, dict)
    }
    verify_result = facts.get("verifyResult") or {"status": "not-run"}
    budget = config.get("verifyBudgetSeconds", _DEFAULT_VERIFY_BUDGET_SECONDS)
    vitals_collected = bool(config.get("vitalsEnabled", True))
    if vitals_collected:
        prev_completeness = {}
        trend = guardian_vitals.read_trend(cwd, root=root, limit=1)
        if trend.get("records"):
            prev_completeness = trend["records"][-1].get("completeness") or {}
        # Do not pass the sweep's injectable `run` into vitals: test doubles stub
        # the verify shell command, while vitals uses `run` only for read-only git.
        vitals_out = guardian_vitals.collect(
            cwd, root=root, lens_results=lens_results,
            verify_result=verify_result, budget_seconds=budget)
        cur_vitals = vitals_out.get("vitals") or {}
        cur_completeness = vitals_out.get("completeness") or {}
        prev_vitals = (prev or {}).get("vitals") or {}
        threshold_notes = []
        vitals_delta = {
            "delta": guardian_vitals.delta(
                prev_vitals, cur_vitals,
                prev_completeness=prev_completeness,
                cur_completeness=cur_completeness),
            "crossings": guardian_vitals.crossings(
                prev_vitals, cur_vitals, thresholds=config.get("thresholds"),
                notes_out=threshold_notes,
                prev_completeness=prev_completeness,
                cur_completeness=cur_completeness),
            "notCollected": vitals_out.get("notCollected") or {},
            "sources": vitals_out.get("sources") or {},
            "completeness": cur_completeness,
            "thresholdNotes": threshold_notes,
        }
    else:
        # Carry prior vitals in the snapshot so re-enabling has a baseline, but mark
        # not-collected so finalize never appends stale numbers as this sweep's.
        cur_vitals = (prev or {}).get("vitals", {})
        vitals_delta = {}

    next_snapshot = {
        "schemaVersion": guardian_store.SNAPSHOT_SCHEMA_VERSION,
        "sweptSha": swept_sha,
        "vitals": cur_vitals,
        "lenses": next_lenses,
    }
    assert set(next_snapshot) == set(guardian_store.SNAPSHOT_KEYS)

    storage_mode = _storage_mode(cwd, root)
    committed = _guardian_committed(cwd, root, storage_mode)

    return {
        "surfaced": surfaced,
        "funnel": {
            "raised": funnel_raised,
            "malformed": malformed,
            "killedByDrift": killed_by_drift,
            "killedByLedger": killed_by_ledger,
            "killedByBench": killed_by_bench,
            "matchNotes": match_notes,
            "trackedFiled": list(ledger_status),
            "degradedLenses": degraded_lenses,
        },
        "lensMeta": lens_meta,
        "redLines": red_lines,
        "factVerdicts": facts["facts"],
        "ledgerStatus": ledger_status,
        "ledgerState": ledger["status"],
        "reportCard": card,
        "reportCardNotes": report_card_notes,
        "vitalsDelta": vitals_delta,
        "vitalsCollected": vitals_collected,
        "nextSnapshot": next_snapshot,
        "prevIdentity": prev_identity,
        "sweptSha": swept_sha,
        "sweepId": sweep_id,
        "filedObservations": filed_observations,
        "committed": committed,
        "storageMode": storage_mode,
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


def _close_filed_records(records, observations, sweep_id):
    """Advance filed records from current metrics → (new_records, advances).

    verified-fixed / reopened run only after the linked issue is confirmed merged or
    closed (§4.7: reopened is merged-but-metric-unmoved). While the issue is still open,
    or its state cannot be determined, the record stays `filed` — the quieter, truthful
    state the collect path already renders as "filed as #N, verification pending"."""
    new_records = list(records or [])
    advances = []
    for rec in list(new_records):
        if not isinstance(rec, dict) or rec.get("disposition") != "filed":
            continue
        rid = rec.get("id")
        if not isinstance(rid, str):
            continue
        obs = (observations or {}).get(rid)
        if obs is None:
            continue
        if not _issue_ready_for_closure(obs.get("issueState")):
            continue
        if not obs.get("present"):
            new_records, result = guardian_ledger.advance(
                new_records, rid, "verified-fixed", sweepId=sweep_id)
            advances.append(result)
            continue
        cand = obs.get("candidate") or {}
        if guardian_ledger.metric_improved(cand, rec):
            new_records, result = guardian_ledger.advance(
                new_records, rid, "verified-fixed", sweepId=sweep_id)
        else:
            new_records, result = guardian_ledger.advance(
                new_records, rid, "reopened", sweepId=sweep_id)
        advances.append(result)
    return new_records, advances


# Allow-list only. A newly introduced reader status must NOT become writable by
# omission — unreadable ledger content is opaque, not empty. `records: []` never
# licenses a rewrite.
_WRITABLE_LEDGER_STATUSES = frozenset(("ok", "absent"))


def _ledger_fully_readable(cwd, root, ledger):
    """May we mutate this ledger?

    Governing rule: an unreadable ledger is opaque, not empty. `records: []` from
    `read_ledger` means "I could not read this" on malformed/newer/unreadable/partial
    — never "there is nothing here." Only an allow-listed status (`ok` / genuine
    `absent`) with every on-disk record accepted by the shared validator (no
    duplicates, no silently-skipped entries) and a schemaVersion exactly equal to
    LEDGER_SCHEMA_VERSION is safe to rewrite."""
    status = ledger.get("status")
    if status not in _WRITABLE_LEDGER_STATUSES:
        return False, "ledger-%s" % (status or "unknown")
    if status == "absent":
        return True, None
    if ledger.get("note"):
        return False, "ledger-duplicate-ids"

    path = guardian_store.ledger_path(cwd, root)
    try:
        with open(path, "rb") as fh:
            text = fh.read().decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return False, "ledger-unreadable"
    block, err = guardian_store._parse_ledger_block(text)
    if err == "ambiguous":
        return False, "ledger-ambiguous"
    if err or not isinstance(block, dict):
        return False, "ledger-malformed"
    ver = block.get("schemaVersion")
    if isinstance(ver, int) and not isinstance(ver, bool) and ver > guardian_store.LEDGER_SCHEMA_VERSION:
        return False, "ledger-newer"
    if not (isinstance(ver, int) and not isinstance(ver, bool)
            and ver == guardian_store.LEDGER_SCHEMA_VERSION):
        return False, "ledger-malformed"
    raw = block.get("records")
    if not isinstance(raw, list):
        return False, "ledger-malformed"
    if "sweeps" in block and not isinstance(block.get("sweeps"), list):
        return False, "ledger-malformed"

    accepted = 0
    for rec in raw:
        if not isinstance(rec, dict):
            return False, "ledger-partial-skip"
        if not all(rec.get(f) is not None for f in guardian_store.LEDGER_MIN_FIELDS):
            return False, "ledger-partial-skip"
        if rec.get("disposition") not in guardian_lens.FINDING_STATES:
            return False, "ledger-partial-skip"
        rid = rec.get("id")
        if not isinstance(rid, str) or not rid.strip():
            return False, "ledger-partial-skip"
        ok, _reasons = guardian_ledger.validate_record(rec)
        if not ok:
            return False, "ledger-partial-skip"
        accepted += 1
    if accepted != len(ledger.get("records") or []):
        return False, "ledger-partial-skip"
    raw_sweeps = block.get("sweeps")
    if isinstance(raw_sweeps, list):
        for entry in raw_sweeps:
            if not isinstance(entry, dict):
                return False, "ledger-partial-skip"
    return True, None


def _closure_status_lines(advances, observations):
    """Human status lines for closure outcomes that land in this sweep's report."""
    lines = []
    for adv in advances or []:
        if not isinstance(adv, dict) or not adv.get("ok"):
            continue
        rid = adv.get("id")
        to = adv.get("to")
        obs = (observations or {}).get(rid) or {}
        issue = obs.get("issue") or ""
        if to == "verified-fixed":
            line = "filed as %s, verified fixed this sweep" % issue
        elif to == "reopened":
            line = "filed as %s, reopened — metric unmoved or worsened" % issue
        else:
            continue
        lines.append({
            "id": rid,
            "lens": guardian_ledger.lens_of(rid) if isinstance(rid, str) else "",
            "line": line,
        })
    return lines


def finalize(cwd, bundle, dispositions, root=None):
    """Transactional finalize: validate → proposed closures → report → vitals → baseline.

    Filed-item closure is computed BEFORE the report is rendered so the durable report
    describes the ledger state this sweep *proposes* to advance to. The advisor's
    `commit_ledger` is the sole writer of `guardian/ledger.md`; this step is read-only
    on the ledger. Order inside the lock: report → vitals trend → snapshot last. The
    snapshot is the commit marker: it is written only after the vitals write succeeds
    (or is an intentional skip). An intentional skip (vitals not collected) does not
    block the baseline; a failed attempted vitals write returns top-level failure and
    leaves `latest.json` untouched so the same bundle can retry."""
    ok, errors = validate_dispositions(bundle, dispositions)
    if not ok:
        return {"ok": False, "reason": "invalid-dispositions", "errors": errors}

    lock_path = guardian_store.sweep_lock_path(cwd, root)
    try:
        file_lock.acquire(lock_path, ttl=guardian_store.SWEEP_LOCK_TTL)
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
        sweep_id = bundle.get("sweepId") or guardian_ledger.make_sweep(
            bundle.get("sweptSha") or "unknown")["sweepId"]

        new_records = list(ledger.get("records") or [])
        advances = []
        writable, skip_why = _ledger_fully_readable(cwd, root, ledger)
        if writable:
            new_records, advances = _close_filed_records(
                ledger["records"], bundle.get("filedObservations"), sweep_id)

        # Report sees proposed closure outcomes before anything is persisted.
        report_bundle = dict(bundle)
        if not writable:
            # Opaque ledger: do not imply "no closures" as if readable-and-empty.
            report_bundle["closuresUnavailable"] = skip_why
            prior = list(bundle.get("ledgerStatus") or [])
            prior.append({
                "id": "(closures)",
                "lens": "guardian",
                "line": "closures deferred — ledger unreadable (%s)" % skip_why,
            })
            report_bundle["ledgerStatus"] = prior
            report_bundle["closureAdvances"] = []
        else:
            report_bundle["closuresUnavailable"] = None
            closure_lines = _closure_status_lines(
                advances, bundle.get("filedObservations"))
            if closure_lines:
                prior = list(bundle.get("ledgerStatus") or [])
                closed_ids = {c["id"] for c in closure_lines}
                prior = [p for p in prior if p.get("id") not in closed_ids]
                report_bundle["ledgerStatus"] = prior + closure_lines
            report_bundle["closureAdvances"] = advances

        report_ledger = {
            "records": new_records,
            "byId": {
                r["id"]: r for r in new_records
                if isinstance(r, dict) and isinstance(r.get("id"), str)
            },
            "status": ledger.get("status"),
            "note": ledger.get("note"),
        }
        report_md = guardian_report.render(report_bundle, dispositions, report_ledger)

        rp = guardian_store.report_path(cwd, root)
        store_core.atomic_write(rp, report_md)

        vitals_append = {"ok": True, "skipped": "no-vitals"}
        try:
            if not bundle.get("vitalsCollected", True):
                vitals_append = {"ok": True, "skipped": "vitals-not-collected"}
            else:
                vitals = (bundle.get("nextSnapshot") or {}).get("vitals") or {}
                completeness = (bundle.get("vitalsDelta") or {}).get("completeness") or {}
                vitals_append = guardian_vitals.append_unlocked(
                    cwd, vitals, sweep_id=sweep_id,
                    swept_sha=bundle.get("sweptSha"), root=root,
                    completeness=completeness)
        except Exception as exc:
            vitals_append = {"ok": False, "reason": str(exc)}

        # Intentional skips (vitals disabled) do not block the baseline.
        # A failed attempted durable vitals write must not advance latest.json.
        # Fail closed: only an explicit ok=True result is non-blocking. A result
        # that happens to carry a `skipped` key with ok=False, or a truthy non-True
        # ok (e.g. ok="failed"), must still block (Fix 6 / WO-1d Fix C) —
        # intentional skips already return ok=True (e.g. vitals-not-collected).
        def _blocks_commit(result):
            return result.get("ok") is not True

        if _blocks_commit(vitals_append):
            return {
                "ok": False,
                "reason": "durable-write-failed",
                "reportPath": rp,
                "vitalsAppend": vitals_append,
            }

        snap_path = guardian_store.snapshot_path(cwd, root)
        # Persist sweepId beside the SNAPSHOT_KEYS baseline (non-identity field)
        # so commit_ledger's additive freshness guard can detect concurrent
        # same-SHA / byte-identical snapshots from a different sweep.
        persisted = {**bundle["nextSnapshot"], "sweepId": bundle["sweepId"]}
        store_core.atomic_write(
            snap_path, json.dumps(persisted, indent=2) + "\n")

        return {
            "ok": True,
            "reportPath": rp,
            "snapshotPath": snap_path,
            "vitalsAppend": vitals_append,
            "closuresUnavailable": report_bundle.get("closuresUnavailable"),
            "closureAdvances": advances if writable else [],
        }
    finally:
        file_lock.release(lock_path)


def commit_ledger(cwd, bundle, dispositions, root=None):
    """Advisor-only ledger commit — the sole writer of `guardian/ledger.md`.

    Run inline at consult/triage AFTER `finalize`. The fenced JSON block and the
    report-card region are **machine-owned** (the advisor is their sole writer); owner
    hand-edits belong to the surrounding prose, which the never-clobber re-splice
    preserves.

    The whole transaction runs under the sweep lock against fresh reads: R1 freshness,
    opaque-ledger check, closure computation, roster read+append, and the never-clobber
    splice write. `finalize` releases its lock before this call, so there is no
    cross-deadlock; this function must call `_write_locked` (not the lock-acquiring
    `write`) because the lock is non-reentrant.

    Fail-closed on opaque/unreadable ledgers, stale bundles (latest.json moved on), and
    transient roster-read failures. Idempotent for a same-identity re-run: already-
    advanced records are skipped by `_close_filed_records`, and `append_sweep` dedups
    on sweep identity."""
    ok, errors = validate_dispositions(bundle, dispositions)
    if not ok:
        return {"ok": False, "reason": "invalid-dispositions", "errors": errors}

    lock_path = guardian_store.sweep_lock_path(cwd, root)
    try:
        file_lock.acquire(lock_path, ttl=guardian_store.SWEEP_LOCK_TTL)
    except file_lock.LockHeld as exc:
        return {"ok": False, "reason": "raced", "lockHeld": exc.holder}

    try:
        # R1 — intent-freshness against FRESH head (under the lock).
        # snapshot_identity hashes only SNAPSHOT_KEYS, so two same-SHA sweeps that
        # produce byte-identical baselines still collide on identity alone. The
        # additive sweepId check is active: finalize persists sweepId beside the
        # baseline (non-identity field), so a concurrent older bundle whose
        # nextSnapshot matches but whose sweepId differs from the head fails closed
        # as stale-bundle rather than landing the wrong closures.
        current = guardian_store.read_snapshot(cwd, root)
        on_disk = guardian_store.snapshot_identity(current)
        expected = guardian_store.snapshot_identity(bundle.get("nextSnapshot") or {})
        if on_disk != expected:
            return {
                "ok": False,
                "reason": "stale-bundle",
                "onDisk": on_disk,
                "expected": expected,
            }
        head_sweep = (current or {}).get("sweepId") if isinstance(current, dict) else None
        bundle_sweep = bundle.get("sweepId")
        if (isinstance(head_sweep, str) and head_sweep.strip()
                and isinstance(bundle_sweep, str) and bundle_sweep.strip()
                and head_sweep.strip() != bundle_sweep.strip()):
            return {
                "ok": False,
                "reason": "stale-bundle",
                "onDisk": on_disk,
                "expected": expected,
                "onDiskSweepId": head_sweep,
                "expectedSweepId": bundle_sweep,
            }

        ledger = guardian_store.read_ledger(cwd, root)
        writable, skip_why = _ledger_fully_readable(cwd, root, ledger)
        if not writable:
            return {
                "ok": False,
                "skipped": skip_why,
                "reason": "ledger write skipped: %s (on-disk bytes left untouched)"
                          % skip_why,
            }

        sweep_id = bundle.get("sweepId") or guardian_ledger.make_sweep(
            bundle.get("sweptSha") or "unknown")["sweepId"]
        new_records, advances = _close_filed_records(
            ledger["records"], bundle.get("filedObservations"), sweep_id)

        # R2 — roster tri-state: read failure fails the commit closed (retryable).
        path = guardian_store.ledger_path(cwd, root)
        roster_status, roster = guardian_ledger._read_sweeps_result(path)
        if roster_status == "read-failed":
            return {
                "ok": False,
                "reason": "roster-read-failed",
                "retryable": True,
            }
        # absent or ok (including genuinely empty): append this sweep normally.
        sweep = guardian_ledger.make_sweep(
            bundle.get("sweptSha") or "unknown", sweep_id=sweep_id)
        sweeps = guardian_ledger.append_sweep(roster, sweep)

        # Report card is derived inside _write_locked from the final merged records —
        # do not reuse collect-time bundle.reportCard (Fix 4).
        result = guardian_ledger._write_locked(
            cwd, new_records, root=root, sweeps=sweeps)
        out = dict(result)
        out["advances"] = advances
        return out
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

    clp = sub.add_parser("commit-ledger")
    clp.add_argument("--cwd", default=".")
    clp.add_argument("--root", default=None)
    clp.add_argument("--bundle", required=True)
    clp.add_argument("--dispositions", required=True)

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
        elif args.cmd == "commit-ledger":
            with open(args.bundle, encoding="utf-8") as fh:
                bundle = json.load(fh)
            with open(args.dispositions, encoding="utf-8") as fh:
                dispositions = json.load(fh)
            out = commit_ledger(args.cwd, bundle, dispositions, root=args.root)
        else:
            # Standalone CLI has no lenses — skip spawning the verify command.
            out = verify_config(args.cwd, root=args.root, needed_facts=set())
    except Exception as exc:
        out = {"error": str(exc)}
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
