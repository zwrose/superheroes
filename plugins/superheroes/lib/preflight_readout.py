"""Pure launch-time preflight readout for the showrunner (spec showrunner-preflight-readout).
Composes the run's OWN resolvers into a JSON-able snapshot and renders it — never a parallel
table, so the readout cannot drift from dispatch. Zero model tokens; stdlib only. Fail-soft:
a per-field read error degrades that one field to 'unavailable' (UFR-2); only a total failure
to build any frame is fail-closed (UFR-3)."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import model_tier
import engine_pref
import engine_adapter  # for the external-engine display model constants (single source of truth)
import model_tier_overrides
import engine_detect

# Bumped to 2 (freeze-consume hardening): a frozenSnapshot persisted by an EARLIER commit of this
# branch carries version 1 but predates the widened merge exclusions (fallbackToClaude/unavailable/
# unrecognized) + the merge-boundary set validation. mergeFrozenSnapshot ignores any snapshot whose
# `version` != this constant (falls through to live config, the documented rollback state), so every
# pre-fix record is treated stale-and-ignored. The JS side learns this value from the snapshot Python
# wrote and, in a drift smoke, from a `python3 -c` dump of this constant — never a hand-duplicated JS
# literal. BUMP this on any change that re-interprets an already-persisted snapshot.
READOUT_VERSION = 2

# The spine's phase roster is the single source of truth. Kept as a literal that MUST equal
# showrunner.js's PHASES; the roster-parity node smoke (Task 12) asserts they match so a phase
# add in the spine fails a test rather than silently under-reporting in the readout.
PHASES = ["plan", "review-plan", "tasks", "review-tasks", "workhorse",
          "review-code", "draft-PR", "test-pilot", "mark-ready", "ship"]

# Per phase: the ordered roles it dispatches. Each role is (roleLabel, model_tier role, role_kind,
# kind-tag). kind-tag drives engine selection (review/build/fix) + the orchestration/None marker.
# 'mark-ready' dispatches no agent (a deterministic spine step): it contributes a single non-agent
# placeholder row (kind "none") so the readout still NAMES every spine phase and the roster stays
# row-for-phase complete against showrunner.js's PHASES (roster-parity guard) — a phase can never
# be silently dropped from the readout. A "none"-kind row pins no engine/model/effort.
_PHASE_ROLES = {
    "plan":         [("author", "author", None, "author")],
    "review-plan":  [("reviewer", "reviewer", "review", "review")],
    "tasks":        [("author", "author", None, "author")],
    "review-tasks": [("reviewer", "reviewer", "review", "review")],
    "workhorse":    [("builder", "builder", "build", "build"),
                     ("per-task reviewer", "reviewer", "review", "review"),
                     ("fixer", "fixer", "fix", "fix"),
                     ("final reviewer", "reviewer-deep", "review", "review-deep")],
    # review-code dispatches the deep reviewer AND a synthesis leaf (FR-2: no dispatching role omitted).
    # The synthesis leaf is LOOP-OWNED native Claude (showrunner.js's reviewCodeLeaves.synthesisLeaf —
    # never engine-routed), so its kind-tag "synthesis" resolves engine "claude" via _engine_for (same
    # as author): _TIER_ROLE.synthesis's pin branch is otherwise unreachable, letting a confirm-window
    # config edit leak into the synthesis model. Model rides the "synthesis" tier role (opus).
    "review-code":  [("deep reviewer", "reviewer-deep", "review", "review-deep"),
                     ("synthesis judge", "synthesis", None, "synthesis")],
    # draft-PR (#219): showrunner.js's composePrBody dispatches a genuine Sonnet leaf ("compose PR
    # body") that composes the durable "what & why" prose BEFORE the deterministic pr_entry.py step
    # opens/adopts the PR — a real dispatch on the "pr-body" model tier, not a no-agent step (the
    # prior single "none" row hid it from frozen preflight snapshots, letting it run on live config
    # after the owner-confirmed readout). Its kind-tag "pr-body" is not review/build/fix, so
    # _engine_for resolves "claude" (matches the real dispatch: composePrBody calls agent() directly,
    # never engine-routed) and _effort_for resolves None (matches: no engine_pref effort applies).
    # The PR-open/adopt step itself is still the deterministic dumb-pipe courier, kept as its own
    # "none" row.
    "draft-PR":     [("compose PR body", "pr-body", None, "pr-body"),
                     ("open/adopt draft PR (deterministic step)", None, None, "none")],
    "test-pilot":   [("orchestration", "orchestrator", None, "orchestration")],
    "mark-ready":   [("no agent (deterministic step)", None, None, "none")],
    "ship":         [("fixer (on CI failure)", "fixer", "fix", "fix")],
}


def _engine_for(kind, prefs):
    """The engine for a role kind. author/orchestration/None-kind roles run on claude (model_tier
    governs); review/build/fix defer to engine_pref."""
    if kind in ("review", "review-deep"):
        return engine_pref.resolve_engine("review", prefs)
    if kind == "build":
        return engine_pref.resolve_engine("build", prefs)
    if kind == "fix":
        return engine_pref.resolve_engine("fix", prefs)
    return "claude"


def _effort_for(engine, kind, prefs):
    effort_overrides = prefs.get("effort") if isinstance(prefs, dict) else None
    role_kind = "review-deep" if kind == "review-deep" else ("review" if kind == "review"
                else ("build" if kind == "build" else ("fix" if kind == "fix" else None)))
    if role_kind is None:
        return None
    return engine_pref.resolve_effort(engine, role_kind, effort_overrides)


def enumerate_dispatch(prefs, tier_overrides, run_overrides=None):
    """The per-(phase,role) dispatch roster. `prefs` = load_engine_prefs shape; `tier_overrides` =
    {role: model}; `run_overrides` = {role: {engine?,model?,effort?}} applied last (FR-11).
    Returns rows in PHASES order; a phase with no dispatching role contributes no row."""
    run_overrides = run_overrides if isinstance(run_overrides, dict) else {}
    tier_overrides = tier_overrides if isinstance(tier_overrides, dict) else {}
    rows = []
    for phase in PHASES:
        for (label, tier_role, _kind_key, kind) in _PHASE_ROLES.get(phase, []):
            if kind == "none":
                # A deterministic spine step that dispatches no agent. It still gets a row so the
                # readout names every phase, but pins no engine/model/effort and is never overridable.
                rows.append({"phase": phase, "role": tier_role, "roleLabel": label,
                             "engine": "claude", "model": None, "effort": None, "kind": kind,
                             "configuredOrDefault": "default"})
                continue
            model = model_tier.resolve_model(tier_role, tier_overrides,
                                             "code" if tier_role == "fixer" else None)
            engine = _engine_for(kind, prefs)
            effort = _effort_for(engine, kind, prefs)
            # FR-5 (second criterion): label each row configured-vs-default. A row is "configured"
            # when the project's model-tier policy carries an EXPLICIT entry for this tier role
            # (the reader returned an owner-set value); otherwise the value fell back to the
            # built-in tier default and the row is "default". Rendered as a per-line [default]
            # label by _phase_line; a run override later re-marks the row overridden (FR-11).
            configured = tier_role in tier_overrides
            row = {"phase": phase, "role": tier_role, "roleLabel": label,
                   "engine": engine, "model": model, "effort": effort, "kind": kind,
                   "configuredOrDefault": "configured" if configured else "default"}
            # UFR-4: a non-orchestration role whose model resolved to None (session inherit) is
            # unexpected — the orchestration role inherits by design (kind == "orchestration"), any
            # other role inheriting is flagged so the owner sees it rather than a silent inherit.
            if model is None and kind != "orchestration":
                row["unexpectedInherit"] = True
            _apply_override(row, run_overrides.get(tier_role))
            rows.append(row)
    return rows


def _apply_override(row, ov):
    """Apply a per-run override to a row in place. Sparse: only fields present are applied. An
    invalid model/effort is flagged (overrideInvalid) not applied (FR-14); an engine outside
    ENGINES is applied-but-marked unrecognized (UFR-5, the owner sees the raw value they asked for)."""
    if not isinstance(ov, dict):
        return row
    applied = False
    if "engine" in ov and isinstance(ov["engine"], str):
        row["engine"] = ov["engine"]
        applied = True
        if ov["engine"] not in engine_pref.ENGINES:
            row["unrecognized"] = True
        # re-derive effort for the (possibly new) engine unless the override also pins effort
        if "effort" not in ov:
            row["effort"] = engine_pref.resolve_effort(row["engine"],
                            ("review-deep" if row["kind"] == "review-deep" else row["kind"]), None)
    if "model" in ov and isinstance(ov["model"], str):
        if ov["model"] in model_tier_overrides.KNOWN_MODELS:
            row["model"] = ov["model"]
            applied = True
        else:
            row["overrideInvalid"] = True
    if "effort" in ov and isinstance(ov["effort"], str):
        if ov["effort"] in _EFFORT_TOKENS:
            row["effort"] = ov["effort"]
            applied = True
        else:
            row["overrideInvalid"] = True
    if applied:
        row["overridden"] = True
    return row


def display_model(engine, model):
    """The model string to SHOW for (engine, model). External engines show the SAME model id
    engine_adapter.build_argv would actually dispatch (single source of truth): codex ignores the
    tier and shows its pinned constant; cursor maps the native tier short-name through
    engine_adapter._CURSOR_MODEL_BY_TIER exactly as build_argv does (fable/opus → their cursor ids;
    an unmapped/None tier → the pinned composer default) — so a per-role model override (e.g.
    author-plan: fable + planAuthor: cursor) is shown honestly, not flattened to the default.
    claude shows the resolved tier model, or 'inherit' for a None (session-inherited) model. An
    unknown engine shows its resolved model raw (UFR-5 handled by the caller's 'unrecognized'
    marker)."""
    if engine == "codex":
        return engine_adapter._CODEX_MODEL
    if engine == "cursor":
        # Mirror build_argv's cursor mapping so the readout never diverges from real dispatch.
        return engine_adapter._CURSOR_MODEL_BY_TIER.get(model, engine_adapter._CURSOR_MODEL)
    if model is None:
        return "inherit"
    return model


def _phase_line(row):
    parts = [row["engine"], display_model(row["engine"], row["model"])]
    if row.get("effort"):
        parts.append(row["effort"])
    disp = " · ".join(parts)
    suffix = " (%s)" % row["roleLabel"]
    if row["kind"] == "orchestration":
        suffix = " (%s — inherits session model, expected)" % row["roleLabel"]
    if row.get("overridden"):
        suffix += " — overridden for this run"
    if row.get("overrideInvalid"):
        suffix += " — recorded override no longer valid, NOT applied ⚠"  # FR-14: shown flagged
    if row.get("fallbackToClaude"):
        suffix += " — %s not authorized → falls back to Claude ⚠" % row["engine"]  # FR-4
    if row.get("unexpectedInherit"):
        suffix += " — UNEXPECTED inherit ⚠"
    if row.get("unrecognized"):
        suffix += " — unrecognized"
    # FR-5 (second criterion): a per-setting configured-vs-default label. A row whose value
    # fell back to a built-in default (configuredOrDefault == "default") is labeled; an
    # explicitly-configured row carries no label (the default-labeling is the signal the spec
    # asks for). Omitted for the orchestration inherit (its "expected" marker already speaks).
    if row.get("configuredOrDefault") == "default" and row["kind"] != "orchestration":
        suffix += " [default]"
    if row.get("unavailable"):
        disp = "unavailable"
        if row.get("unavailableReason"):
            disp += " (%s)" % row["unavailableReason"]
    return "  %-16s %s%s" % (row["phase"], disp, suffix)


def render(snapshot):
    """Pure text rendering of a snapshot (spec's UI sketch is the target shape). ≤40 lines for the
    default pipeline + one external engine (NFR scannability, asserted by a test)."""
    lines = ["Showrunner preflight — %s" % snapshot.get("workItem", ""), "", "Phases & dispatch"]
    for row in snapshot.get("phases", []):
        lines.append(_phase_line(row))
    lines.append("")
    ext = snapshot.get("externalEngines") or {}
    if ext:
        parts = []
        for eng, rec in ext.items():
            parts.append("%s: %s" % (eng, "authorized" if rec.get("authorized") else "NOT authorized"))
        lines.append("External engines   " + "   ·   ".join(parts))
    cal = snapshot.get("calibration") or {}
    lines.append("Calibration        " + ("provisional (not owner-confirmed) ⚠"
                 if cal.get("provisional") else "confirmed"))
    verify = snapshot.get("verify") or {}
    cmd = verify.get("command")
    lines.append("Verify             " + ("unverified" if cmd in (None, "none") else cmd))
    storage = snapshot.get("storage") or {}
    lines.append("Storage            %s · docs at %s"
                 % (storage.get("mode", "unavailable"), storage.get("docsPath", "unavailable")))
    # Privacy note (spec NFR): verify/storage strings echo verbatim, owner-only. Revisit redaction
    # before ever routing readout content to a shared destination (out of scope here).
    return "\n".join(lines)


_EFFORT_TOKENS = ("none", "low", "medium", "high", "xhigh", "composer")


def preflight_readout_engines():
    return list(engine_pref.ENGINES)


def validate_override(role, field, value, snapshot):
    """Pure. ok:false + accepted set for an invalid engine/model/effort (UFR-6) or the
    non-overridable orchestration role (FR-10). ok:true echoing the concrete value otherwise.
    Accepted sets come from the resolvers' own domains — never re-hardcoded here."""
    if role == "orchestrator":
        return {"ok": False, "reason": "the orchestration role is session-inherited and not overridable"}
    if field == "engine":
        if isinstance(value, str) and value in engine_pref.ENGINES:
            return {"ok": True, "accepted": value}
        return {"ok": False, "acceptedValues": list(engine_pref.ENGINES),
                "reason": "not a valid engine"}
    if field == "model":
        if isinstance(value, str) and value in model_tier_overrides.KNOWN_MODELS:
            return {"ok": True, "accepted": value}
        return {"ok": False, "acceptedValues": list(model_tier_overrides.KNOWN_MODELS),
                "reason": "not a valid model"}
    if field == "effort":
        if isinstance(value, str) and value in _EFFORT_TOKENS:
            return {"ok": True, "accepted": value}
        return {"ok": False, "acceptedValues": list(_EFFORT_TOKENS),
                "reason": "not a valid effort"}
    return {"ok": False, "reason": "field must be one of engine, model, effort"}


# --- Task 4: assemble — compose the snapshot from the real readers (FR-4/5/6/7, UFR-2/3) ---

_RAISE = object()  # sentinel: a per-field read error (test-injected OR a real read that raised)


def _read_field(fn):
    """Run one field's reader; return _RAISE (never propagate) on ANY exception, so a single source
    raising degrades only that field. This is the per-field guard the UFR-2 fail-soft claim rests on
    — _load_readers wraps EVERY real read in it, so no one source can collapse the whole readout."""
    try:
        return fn()
    except Exception:
        return _RAISE


def _load_readers(work_item, root):
    """Real-reader loader: read each source once via its existing reader, EACH wrapped in _read_field
    so a raise degrades that one field to _RAISE (assemble maps _RAISE -> unavailable + degraded[]),
    never the whole readout. Only the shared setup (profile path) can raise past this into UFR-3.

    `root` is the repo working tree (the CLI's --root == `git rev-parse --show-toplevel`). It is the
    `cwd` every reader wants — NEVER the store-base override. The store-base is a distinct test seam:
    readers that take it as their `root`/`store_root` second arg default it to None so the REAL store
    (control_plane.store_root(), via the ~/.claude/superheroes seam) resolves. Passing the repo root
    into that store-base slot collapses two different parameters and resolves calibration under a
    never-existing <repo>/projects/<key>/config/core.md — the fail-open then silently degrades the
    whole readout to the provisional/all-Claude fallback (this is the #221 recurrence: engine_pref
    and core_md, plus mode_registry, take (cwd, store-base) — not (root, root)). Readers whose single
    arg IS the repo cwd (resolve_profile_path, engine_detect.probe, verify_command_cli.resolve_command)
    correctly receive `root`; definition_doc.resolve_work_item_dir's `root`/`cwd` ARE the repo, its
    store_root seam defaults to None."""
    import core_md, verify_command_cli, mode_registry, definition_doc
    import engine_pref as _ep
    # Shared setup — a raise here has no single owning field, so it (correctly) escapes to assemble's
    # total-failure guard (UFR-3), not a per-field degrade. resolve_profile_path's arg is the repo cwd.
    profile = model_tier_overrides.resolve_profile_path(root)
    # Per-field reads — each independently guarded so one raise degrades only its own field (UFR-2).
    # (cwd=root, store-base=None) for every reader whose second arg is the store-base seam.
    prefs = _read_field(lambda: _ep.load_engine_prefs(root, None))
    tier_overrides = _read_field(lambda: model_tier_overrides.load_overrides(profile))
    authz = _read_field(lambda: engine_detect.probe(root))  # probe's arg is the git cwd (repo)
    calibration = _read_field(
        lambda: {"status": (core_md.read(root, None) or {}).get("status", "provisional")})
    verify = _read_field(lambda: verify_command_cli.resolve_command(root))  # arg is the repo cwd
    storage = _read_field(lambda: {"mode": mode_registry.resolve(root, None)["mode"],
                                   "docsPath": definition_doc.resolve_work_item_dir(
                                       work_item, root=root, cwd=root)})  # root/cwd = repo; store_root=None
    return {"prefs": prefs, "tier_overrides": tier_overrides, "authz": authz,
            "calibration": calibration, "verify": verify, "storage": storage}


def assemble(work_item, root, run_overrides=None, readers=None, _force_total_failure=False):
    """Read config once, enumerate the roster, apply run_overrides, return the snapshot. Fail-soft
    per field (UFR-2); fail-closed only when no frame can be built (UFR-3)."""
    if _force_total_failure:
        return {"ok": False, "reason": "readout could not be assembled",
                "remediation": "re-run the band's init so the profile + storage config resolve"}
    if readers is None:
        try:
            readers = _load_readers(work_item, root)
        except Exception as exc:
            return {"ok": False, "reason": "readout could not be assembled (%s)" % type(exc).__name__,
                    "remediation": "re-run the band's init so the profile + storage config resolve"}
    degraded = []

    def _field(name, default):
        """Read one field; a _RAISE (a per-field read that raised in _load_readers, or a test
        sentinel) degrades to `default` + a degraded[] entry — the UFR-2 fail-soft path."""
        v = readers.get(name)
        if v is _RAISE:
            degraded.append({"field": name, "reason": "%s unreadable" % name})
            return default
        return v

    prefs = _field("prefs", None) or {"reviewer": "claude", "implementation": "claude", "effort": {}}
    tier_overrides = _field("tier_overrides", None) or {}
    phases = enumerate_dispatch(prefs, tier_overrides, run_overrides)

    authz = _field("authz", None) or {}
    external = {}
    for eng in ("codex", "cursor"):
        if any(r["engine"] == eng for r in phases):
            ok, _cause, _rem = engine_detect.decide(authz, eng)
            external[eng] = {"authorized": bool(ok)}
    for r in phases:
        if r["engine"] in external and not external[r["engine"]]["authorized"]:
            r["fallbackToClaude"] = True

    cal = _field("calibration", {"status": "provisional"}) or {"status": "provisional"}
    provisional = cal.get("status") != "confirmed"

    verify_val = readers.get("verify")
    verify = {"command": verify_val if verify_val is not _RAISE else None}
    if verify_val is _RAISE:
        degraded.append({"field": "verify", "reason": "verify command unreadable"})
        verify["unavailable"] = True

    storage_val = readers.get("storage")
    if storage_val is _RAISE:
        degraded.append({"field": "storage", "reason": "storage mode unreadable"})
        storage = {"unavailable": True}
    else:
        storage = storage_val or {"unavailable": True}

    return {"workItem": work_item, "phases": phases, "externalEngines": external,
            "calibration": {"status": (cal or {}).get("status"), "provisional": provisional},
            "verify": verify, "storage": storage, "degraded": degraded,
            "version": READOUT_VERSION}


# --- Task 7: The JSON CLI (main) — the verified interface the skill shells (FR-1 plumbing, UFR-3) ---


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(prog="preflight_readout")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("assemble")
    a.add_argument("--work-item", required=True)
    a.add_argument("--root", default=".")
    a.add_argument("--run-overrides", default=None, help="optional JSON {role:{engine?,model?,effort?}}")
    r = sub.add_parser("render")
    r.add_argument("--snapshot", required=True, help="a snapshot JSON string (from assemble)")
    v = sub.add_parser("validate-override")
    v.add_argument("--role", required=True)
    v.add_argument("--field", required=True, choices=("engine", "model", "effort"))
    v.add_argument("--value", required=True)
    args = ap.parse_args(argv)
    if args.cmd == "assemble":
        ro = None
        if args.run_overrides:
            try:
                ro = json.loads(args.run_overrides)
            except (ValueError, json.JSONDecodeError):
                ro = None
        snap = assemble(args.work_item, args.root, ro)
        sys.stdout.write(json.dumps(snap) + "\n")
        return 0 if snap.get("ok", True) is not False else 1  # UFR-3: total failure -> non-zero
    if args.cmd == "render":
        try:
            snap = json.loads(args.snapshot)
        except (ValueError, json.JSONDecodeError):
            sys.stdout.write("readout unavailable (unreadable snapshot)\n")
            return 1
        sys.stdout.write(render(snap) + "\n")
        return 0
    if args.cmd == "validate-override":
        out = validate_override(args.role, args.field, args.value, {})
        sys.stdout.write(json.dumps(out) + "\n")
        return 0 if out.get("ok") else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
