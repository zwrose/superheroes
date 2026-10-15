---
superheroes: doc
schemaVersion: 1
docType: tasks
workItem: showrunner-preflight-readout-f7c1e0
issue: null
size: large
status: approved
gates: {review: passed}
producedBy: "the-architect@0.5.0"
created: "2026-07-03"
updated: "2026-07-05"
---
# Showrunner preflight readout — Tasks

## Goal

Add a deterministic, zero-token **launch-time preflight readout** to the showrunner: a new
Start step 1.5 that renders, in plain language, exactly what the confirmed run will dispatch —
engine, model, and effort per phase/role — plus external-engine authorization, calibration
provisional-ness, the verify command, and the storage mode with doc read/write locations. The
owner reads it, may override any overridable role's engine/model/effort for this run, then
confirms; only then does the first agent dispatch. On confirm the render is frozen and the run
dispatches from the frozen snapshot (never re-read config), so a post-render config edit never
changes what runs; overrides persist with the run and are reapplied + re-validated on relaunch.

The build is test-first and additive. A new pure Python core (`lib/preflight_readout.py`) composes
the run's *existing* resolvers (`model_tier`, `engine_pref`, `engine_detect`,
`model_tier_overrides`, `verify_command_cli`, `mode_registry`, `core_md`, `definition_doc`) into a
JSON-able snapshot and renders it — never a parallel table, so the readout cannot drift from
dispatch. A new durable seam (`lib/run_overrides.py`) persists the accepted overrides + frozen
snapshot on the control-plane run record. The showrunner SKILL gains the one interactive
confirm/override loop, and the spine (`showrunner.js`) gains a single additive pin-or-resolve fork
so a pinned snapshot value dispatches while an unavailable field resolves live. Every task lands
with its test; the doc is done when the whole gate (3 validators + pytest + node smokes) is green
on `main` at or after PR #163.

## Architecture

The readout slots between the existing pre-flight gate (SKILL step 1, unchanged) and the bundle
launch (SKILL step 2) as a new **step 1.5**:

```
launch → preflight.py gate (unchanged)                         [SKILL step 1]
           │ ok:true
           ▼
       preflight_readout.assemble(work_item, root, run_overrides)   [NEW pure]
           │  → snapshot (plain dict)
           ▼
       preflight_readout.render(snapshot)                      [NEW pure] → terminal text
           │
       ── SKILL confirm/override loop ──                       [SKILL step 1.5, the one interactive surface]
           │   confirm → run_overrides.write(freeze) → launch bundle
           │   override → validate_override → re-assemble → re-render → re-confirm
           │   decline  → abort, no side effects (UFR-1)
           ▼
       bundle launch (Workflow tool)                           [SKILL step 2]
           │   startup reads the frozen snapshot → pins __SR_OVERRIDES / __SR_ENGINE_PREFS
           │   spine's pin-or-resolve fork dispatches each phase from the frozen value (FR-8)
```

Three layers, each on an existing band boundary:

1. **`lib/preflight_readout.py` (new, pure core).** In the deterministic-decider family alongside
   `preflight.py` / `run_readout.py` / `readout.py`. `enumerate_dispatch` builds the phase/role
   roster by walking the spine's `PHASES` (imported byte-for-byte from `showrunner.js`) and, per
   phase, the roles it dispatches, resolving each through `model_tier.resolve_model` +
   `engine_pref.resolve_engine` / `resolve_effort`. `assemble` does the disk reads once, calls
   `enumerate_dispatch`, applies `run_overrides`, and returns the snapshot; `render` prints it;
   `validate_override` gate-keeps an override; a JSON `main()` mirrors `preflight.py`'s CLI so the
   skill shells the verified interface.

2. **`lib/run_overrides.py` (new, durable seam).** `read` / `write` against the control-plane run
   record (`control_plane.py` store — the substrate the run's journal/checkpoint/resume already
   use). Overrides persist as `{role: {engine?, model?, effort?}}`; the frozen snapshot is stored
   alongside. Fail-open on an unreadable/older record (→ no overrides, resolve live), matching the
   band's model/engine fail-open posture.

3. **`skills/showrunner/SKILL.md` (changed) + `lib/showrunner.js` (changed, one additive fork).**
   The skill adds step 1.5 (shell assemble/render, host ask primitive for confirm/override/decline).
   The spine's startup pipe, which already plants `__SR_OVERRIDES` (model tiers) and
   `__SR_ENGINE_PREFS` (engine + effort) as globals the twin resolve sites read, gains a
   frozen-snapshot lookup: a pinned per-role value seeds those globals so dispatch honors the frozen
   value; an unpinned (unavailable) field resolves live exactly as today. This is behavior-preserving
   when no snapshot is present (the rollback state).

The whole surface is read-mostly and deterministic: the only writes are the durable override record
+ frozen snapshot, both keyed to the run. The no-drift guarantee is structural — there is exactly
one code path from "what dispatches" to "what the readout shows": the shared resolvers.

## Tech Stack

- **Python 3 (stdlib only)** for the pure core (`lib/preflight_readout.py`) and the durable seam
  (`lib/run_overrides.py`), matching every existing `lib/*.py` decider — no new package or service.
  Reused unchanged: `model_tier.resolve_model`, `engine_pref.resolve_engine` / `resolve_effort` /
  `load_engine_prefs`, `engine_detect.probe` / `decide`, `model_tier_overrides.load_overrides` /
  `KNOWN_MODELS`, `engine_pref.ENGINES`, `engine_adapter._CODEX_MODEL` / `_CURSOR_MODEL`,
  `verify_command_cli.resolve_command`, `mode_registry.read_registry` / `resolve`, `core_md.read`,
  `definition_doc.resolve_work_item_dir`, `control_plane` (store paths + `atomic_write`).
- **Node.js twins** (`model_tier.js` / `engine_pref.js`) and the spine `showrunner.js` for the
  one dispatch-read fork; the frozen snapshot seeds the existing `__SR_OVERRIDES` /
  `__SR_ENGINE_PREFS` globals the twins already read.
- **Markdown** for `skills/showrunner/SKILL.md` (the interactive step is prose narrating host-neutral
  actions, resolved via the host tool map — the pattern already in the file for the pre-flight gate).
- **pytest** for the Python units (mirroring `lib/tests/test_preflight.py` — inject probes/readers,
  never hit disk or the network in a unit) and **Node smoke tests** in `lib/tests/*_smoke.js` (run by
  the pytest wrapper) for the roster-parity and pin-or-resolve spine behaviors.
- **CI gate** (run locally before pushing): `validate_marketplace.py`, `validate_hosts.py`,
  `validate_skills.py`, then `pytest` over `.github/scripts/tests/`,
  `plugins/superheroes/lib/tests/`, `plugins/superheroes/eval/tests/`, `eval/lib/tests/`.

## Tasks

### Task 1: enumerate_dispatch — the phase/role roster (FR-2, FR-5 configured-vs-default)

Write `plugins/superheroes/lib/tests/test_preflight_readout.py` first. Assert that
`preflight_readout.enumerate_dispatch(prefs, tier_overrides, run_overrides=None)` returns a list of
per-role dicts — one entry per `(phase, role)` the showrunner dispatches — each carrying
`phase`, `role`, `roleLabel`, `engine`, `model`, `effort`, and `kind`. Pin the shape with concrete
inputs:

```python
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import preflight_readout

def _claude_prefs():
    return {"reviewer": "claude", "implementation": "claude", "effort": {}}

def test_roster_phase_set_equals_spine_PHASES():
    rows = preflight_readout.enumerate_dispatch(_claude_prefs(), {})
    phases = []
    for r in rows:
        if r["phase"] not in phases:
            phases.append(r["phase"])
    assert phases == list(preflight_readout.PHASES)  # PHASES imported from the spine roster

def test_build_phase_yields_four_roles():
    rows = preflight_readout.enumerate_dispatch(_claude_prefs(), {})
    build = [r for r in rows if r["phase"] == "workhorse"]
    kinds = [r["kind"] for r in build]
    assert kinds == ["build", "review", "fix", "review-deep"]  # builder, per-task reviewer, fixer, final reviewer

def test_each_row_carries_engine_model_effort():
    rows = preflight_readout.enumerate_dispatch(_claude_prefs(), {})
    for r in rows:
        assert set(("phase", "role", "roleLabel", "engine", "model", "effort", "kind",
                    "configuredOrDefault")) <= set(r)

def test_unconfigured_role_labeled_default_configured_role_labeled_configured():
    # FR-5 second criterion: an empty tier-override map -> every row is a "default"; an explicit
    # per-role override -> that row is "configured".
    default_rows = preflight_readout.enumerate_dispatch(_claude_prefs(), {})
    assert all(r["configuredOrDefault"] == "default" for r in default_rows)
    configured_rows = preflight_readout.enumerate_dispatch(_claude_prefs(), {"reviewer": "opus"})
    rev = [r for r in configured_rows if r["role"] == "reviewer"][0]
    assert rev["configuredOrDefault"] == "configured"
    author = [r for r in configured_rows if r["role"] == "author"][0]
    assert author["configuredOrDefault"] == "default"

def test_claude_prefs_yield_claude_engine_and_none_effort():
    rows = preflight_readout.enumerate_dispatch(_claude_prefs(), {})
    for r in rows:
        if r["kind"] != "orchestration":
            assert r["engine"] == "claude"
            assert r["effort"] is None  # engine_pref.resolve_effort returns None for claude

def test_orchestration_role_inherits_session_model():
    rows = preflight_readout.enumerate_dispatch(_claude_prefs(), {})
    orch = [r for r in rows if r["kind"] == "orchestration"]
    assert len(orch) == 1
    assert orch[0]["model"] is None  # inherit
```

Then create `plugins/superheroes/lib/preflight_readout.py` with a module-level roster map and
`enumerate_dispatch`. Import `PHASES` from the spine so a phase add surfaces in the parity test
rather than in production:

```python
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

READOUT_VERSION = 1

# The spine's phase roster is the single source of truth. Kept as a literal that MUST equal
# showrunner.js's PHASES; the roster-parity node smoke (Task 12) asserts they match so a phase
# add in the spine fails a test rather than silently under-reporting in the readout.
PHASES = ["plan", "review-plan", "tasks", "review-tasks", "workhorse",
          "review-code", "draft-PR", "test-pilot", "mark-ready", "ship"]

# Per phase: the ordered roles it dispatches. Each role is (roleLabel, model_tier role, role_kind,
# kind-tag). kind-tag drives engine selection (review/build/fix) + the orchestration/None marker.
# 'draft-PR' and 'mark-ready' dispatch no agent (deterministic spine steps) -> no rows.
_PHASE_ROLES = {
    "plan":         [("author", "author", None, "author")],
    "review-plan":  [("reviewer", "reviewer", "review", "review")],
    "tasks":        [("author", "author", None, "author")],
    "review-tasks": [("reviewer", "reviewer", "review", "review")],
    "workhorse":    [("builder", "mechanical", "build", "build"),
                     ("per-task reviewer", "reviewer", "review", "review"),
                     ("fixer", "fixer", "fix", "fix"),
                     ("final reviewer", "reviewer-deep", "review", "review-deep")],
    "review-code":  [("deep reviewer", "reviewer-deep", "review", "review-deep")],
    "draft-PR":     [],
    "test-pilot":   [("orchestration", "orchestrator", None, "orchestration")],
    "mark-ready":   [],
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
            _apply_override(row, run_overrides.get(tier_role))
            rows.append(row)
    return rows


def _apply_override(row, ov):
    """Apply a per-run override (engine/model/effort) to a row in place, marking it overridden.
    A None/empty override is a no-op. Filled in by Task 5."""
    return row
```

Run `python3 -m pytest plugins/superheroes/lib/tests/test_preflight_readout.py -q` and confirm the
five tests pass. Do NOT yet wire `_apply_override` (Task 5) or `assemble` (Task 4).

### Task 2: The engine→model display rule + render (FR-2, NFR scannability)

Add tests to `test_preflight_readout.py` for the display mapping and the renderer:

```python
def test_display_model_maps_external_engines():
    assert preflight_readout.display_model("codex", "sonnet") == "gpt-5.5"
    # cursor honors the SAME per-tier map build_argv uses: an unmapped tier shows the pinned default,
    # a mapped tier (today only fable/opus via _CURSOR_MODEL_BY_TIER) shows its resolved cursor id.
    assert preflight_readout.display_model("cursor", "sonnet") == "composer-2.5-fast"
    assert preflight_readout.display_model("cursor", None) == "composer-2.5-fast"
    assert preflight_readout.display_model("cursor", "fable") == "claude-fable-5-thinking-xhigh"
    assert preflight_readout.display_model("cursor", "opus") == "claude-opus-4-8-thinking-high"
    assert preflight_readout.display_model("claude", "opus") == "opus"
    assert preflight_readout.display_model("claude", None) == "inherit"

def _snapshot_default():
    # a minimal well-formed snapshot for the default claude pipeline (Task 4 shape)
    rows = preflight_readout.enumerate_dispatch(_claude_prefs(), {})
    return {"workItem": "wi", "phases": rows,
            "externalEngines": {}, "calibration": {"status": "confirmed", "provisional": False},
            "verify": {"command": "npm test"}, "storage": {"mode": "global", "docsPath": "/p/docs"},
            "degraded": [], "version": preflight_readout.READOUT_VERSION}

def test_render_is_str_and_names_every_phase():
    text = preflight_readout.render(_snapshot_default())
    assert isinstance(text, str)
    for phase in ("plan", "review-plan", "tasks", "review-tasks", "workhorse",
                  "review-code", "test-pilot", "ship"):
        assert phase in text

def test_render_orchestration_marked_expected():
    text = preflight_readout.render(_snapshot_default())
    assert "inherits session model" in text and "expected" in text

def test_render_default_pipeline_one_engine_is_at_most_40_lines():
    snap = _snapshot_default()
    snap["externalEngines"] = {"codex": {"authorized": True}}
    text = preflight_readout.render(snap)
    assert len([ln for ln in text.splitlines()]) <= 40

def test_render_shows_fallback_to_claude_flag_on_the_row():
    # FR-4 (premortem-001): a role whose engine is unauthorized is flagged on ITS OWN phase row
    # in render(), not only in the External-engines summary line.
    snap = _snapshot_default()
    snap["phases"][1]["fallbackToClaude"] = True  # a review row
    text = preflight_readout.render(snap)
    assert "falls back to Claude" in text

def test_render_shows_override_invalid_flag_on_the_row():
    # FR-14 (premortem-001): a recorded override that is no longer valid is shown flagged on its
    # row, not silently applied — asserted against render()'s actual output.
    snap = _snapshot_default()
    snap["phases"][1]["overrideInvalid"] = True
    text = preflight_readout.render(snap)
    assert "no longer valid" in text

def test_render_labels_a_default_row():
    # FR-5 second criterion: a row that fell back to a built-in default is labeled [default].
    snap = _snapshot_default()
    snap["phases"][0]["configuredOrDefault"] = "default"
    text = preflight_readout.render(snap)
    assert "[default]" in text
```

Implement in `preflight_readout.py`:

```python
import engine_adapter  # for the external-engine display model constants (single source of truth)


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
```

Run the pytest file; confirm the new tests pass alongside Task 1's.

### Task 3: validate_override — the pure override gate (FR-10, UFR-6)

Add tests:

```python
def _rows_by_role():
    return {r["role"]: r for r in preflight_readout.enumerate_dispatch(_claude_prefs(), {})}

def test_valid_engine_override_accepted():
    snap = _snapshot_default()
    out = preflight_readout.validate_override("reviewer", "engine", "codex", snap)
    assert out["ok"] is True and out["accepted"] == "codex"

def test_invalid_engine_rejected_with_accepted_values():
    snap = _snapshot_default()
    out = preflight_readout.validate_override("reviewer", "engine", "gpt", snap)
    assert out["ok"] is False
    assert set(out["acceptedValues"]) == set(preflight_readout_engines())  # engine_pref.ENGINES

def test_invalid_model_rejected_with_accepted_values():
    snap = _snapshot_default()
    out = preflight_readout.validate_override("reviewer", "model", "gpt5", snap)
    assert out["ok"] is False
    assert "sonnet" in out["acceptedValues"] and "opus" in out["acceptedValues"]

def test_orchestration_role_is_not_overridable():
    snap = _snapshot_default()
    out = preflight_readout.validate_override("orchestrator", "model", "opus", snap)
    assert out["ok"] is False and "orchestration" in out["reason"].lower()

def test_effort_override_valid_for_codex():
    snap = _snapshot_default()
    out = preflight_readout.validate_override("reviewer", "effort", "xhigh", snap)
    assert out["ok"] is True and out["accepted"] == "xhigh"

def test_unknown_field_rejected():
    snap = _snapshot_default()
    out = preflight_readout.validate_override("reviewer", "storage", "x", snap)
    assert out["ok"] is False
```

Add a tiny helper the test references and the validator in `preflight_readout.py`:

```python
import model_tier_overrides

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
```

Run the pytest file; confirm all Task 1–3 tests pass.

### Task 4: assemble — compose the snapshot from the real readers (FR-4/5/6/7, UFR-2/3)

Add tests that inject the readers so the unit never touches disk or the network. Follow
`test_preflight.py`'s injection pattern (pass the collaborators in, assert the pure result):

```python
def _fake_readers(**over):
    base = {
        "prefs": {"reviewer": "claude", "implementation": "claude", "effort": {}},
        "tier_overrides": {},
        "authz": {"codex": {"installed": True, "authed": True, "error": None},
                  "cursor": {"installed": True, "authed": True, "error": None}},
        "calibration": {"status": "provisional"},
        "verify": "npm test",
        "storage": {"mode": "global", "docsPath": "/proj/docs"},
    }
    base.update(over)
    return base

def test_assemble_returns_snapshot_shape():
    snap = preflight_readout.assemble("wi", "/root", readers=_fake_readers())
    for key in ("workItem", "phases", "externalEngines", "calibration",
                "verify", "storage", "degraded", "version"):
        assert key in snap
    assert snap["version"] == preflight_readout.READOUT_VERSION

def test_provisional_calibration_flagged():
    snap = preflight_readout.assemble("wi", "/root", readers=_fake_readers())
    assert snap["calibration"]["provisional"] is True

def test_unverified_when_command_is_none():
    snap = preflight_readout.assemble("wi", "/root", readers=_fake_readers(verify="none"))
    assert snap["verify"]["command"] in ("none", None)

def test_storage_mode_and_docs_path_present():
    snap = preflight_readout.assemble("wi", "/root", readers=_fake_readers())
    assert snap["storage"]["mode"] == "global"
    assert snap["storage"]["docsPath"] == "/proj/docs"

def test_external_engine_authorization_reported():
    readers = _fake_readers(prefs={"reviewer": "codex", "implementation": "claude", "effort": {}},
                            authz={"codex": {"installed": True, "authed": False, "error": None},
                                   "cursor": {"installed": False, "authed": False, "error": None}})
    snap = preflight_readout.assemble("wi", "/root", readers=readers)
    assert snap["externalEngines"]["codex"]["authorized"] is False
    # a role whose engine is unauthorized is flagged fallbackToClaude
    review = [r for r in snap["phases"] if r["kind"] == "review"][0]
    assert review.get("fallbackToClaude") is True

def test_one_field_error_degrades_not_fails(monkeypatch=None):
    readers = _fake_readers(storage=preflight_readout._RAISE)  # sentinel: this reader raises
    snap = preflight_readout.assemble("wi", "/root", readers=readers)
    assert any(d for d in snap["degraded"] if d.get("field") == "storage")
    assert snap["storage"].get("unavailable") is True

def test_total_failure_returns_failure_sentinel():
    snap = preflight_readout.assemble("wi", "/root", readers=None, _force_total_failure=True)
    assert snap.get("ok") is False and snap.get("reason")
```

Implement `assemble` in `preflight_readout.py`. The `readers` param defaults to a real-reader
loader (`_load_readers`) that wraps **each disk read individually** (via `_read_field` below, which
returns the `_RAISE` sentinel on any exception); a test passes a fake dict. Because each field is
guarded at read time, one source raising (e.g. `mode_registry.resolve`) yields `_RAISE` for that one
field — which `assemble` degrades to `unavailable` + a `degraded[]` entry (UFR-2) exactly as it does
for the test sentinel — while every other field is still read. `_load_readers` NEVER lets a
single-field raise escape: the only path to the total-failure sentinel (`{"ok": False, "reason": ...}`,
UFR-3) is the import/setup work before the per-field reads (e.g. resolving the profile path) failing,
which no single config source owns:

```python
import engine_detect

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
    never the whole readout. Only the shared setup (profile path) can raise past this into UFR-3."""
    import core_md, verify_command_cli, mode_registry, definition_doc
    import engine_pref as _ep
    # Shared setup — a raise here has no single owning field, so it (correctly) escapes to assemble's
    # total-failure guard (UFR-3), not a per-field degrade.
    profile = model_tier_overrides.resolve_profile_path(root)
    # Per-field reads — each independently guarded so one raise degrades only its own field (UFR-2).
    prefs = _read_field(lambda: _ep.load_engine_prefs(root, root))
    tier_overrides = _read_field(lambda: model_tier_overrides.load_overrides(profile))
    authz = _read_field(lambda: engine_detect.probe(root))
    calibration = _read_field(
        lambda: {"status": (core_md.read(root, root) or {}).get("status", "provisional")})
    verify = _read_field(lambda: verify_command_cli.resolve_command(root))
    storage = _read_field(lambda: {"mode": mode_registry.resolve(root, root)["mode"],
                                   "docsPath": definition_doc.resolve_work_item_dir(
                                       work_item, root=root, cwd=root)})
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
```

Run the pytest file; confirm all Task 1–4 tests pass. (The two `_RAISE`/total-failure tests pin
the fail-soft vs fail-closed split.)

### Task 5: Apply run overrides + re-validate on relaunch (FR-11, FR-14, UFR-5)

Add tests:

```python
def test_override_marks_row_and_takes_value():
    ro = {"reviewer": {"engine": "codex", "effort": "xhigh"}}
    rows = preflight_readout.enumerate_dispatch(_claude_prefs(), {}, ro)
    rev = [r for r in rows if r["role"] == "reviewer" and r["phase"] == "review-plan"][0]
    assert rev["engine"] == "codex" and rev["effort"] == "xhigh"
    assert rev["overridden"] is True

def test_non_overridden_rows_unchanged():
    ro = {"reviewer": {"engine": "codex"}}
    base = preflight_readout.enumerate_dispatch(_claude_prefs(), {})
    with_ov = preflight_readout.enumerate_dispatch(_claude_prefs(), {}, ro)
    author_base = [r for r in base if r["phase"] == "plan"][0]
    author_ov = [r for r in with_ov if r["phase"] == "plan"][0]
    assert author_base == author_ov  # no override on author -> byte-identical

def test_unrecognized_engine_marked_not_dropped():
    ro = {"reviewer": {"engine": "quantum"}}  # not in ENGINES
    rows = preflight_readout.enumerate_dispatch(_claude_prefs(), {}, ro)
    rev = [r for r in rows if r["role"] == "reviewer" and r["phase"] == "review-plan"][0]
    assert rev["engine"] == "quantum" and rev.get("unrecognized") is True

def test_reapply_revalidate_flags_now_invalid_override():
    # a recorded override that is no longer a valid option is flagged, not silently applied (FR-14)
    ro = {"reviewer": {"model": "gpt5"}}  # not in KNOWN_MODELS
    rows = preflight_readout.enumerate_dispatch(_claude_prefs(), {}, ro)
    rev = [r for r in rows if r["role"] == "reviewer" and r["phase"] == "review-plan"][0]
    assert rev.get("overrideInvalid") is True
```

Implement `_apply_override` (replacing the Task 1 stub) in `preflight_readout.py`:

```python
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
```

Run the pytest file; confirm all Task 1–5 tests pass.

### Task 6: UFR-4 — flag an unexpected inherit (a non-orchestration role that resolves to None)

Add a test:

```python
def test_non_orchestration_none_model_flagged_unexpected():
    # a tier override that maps a normal role to None (session inherit) must be shown flagged
    rows = preflight_readout.enumerate_dispatch(_claude_prefs(), {"author": None})
    author = [r for r in rows if r["role"] == "author"][0]
    assert author["model"] is None
    assert author.get("unexpectedInherit") is True

def test_orchestration_none_is_not_unexpected():
    rows = preflight_readout.enumerate_dispatch(_claude_prefs(), {})
    orch = [r for r in rows if r["kind"] == "orchestration"][0]
    assert orch["model"] is None
    assert not orch.get("unexpectedInherit")
```

In `enumerate_dispatch`, after building `row` (before `_apply_override`), mark the unexpected
inherit:

```python
            if model is None and kind != "orchestration":
                row["unexpectedInherit"] = True
```

Run the pytest file; confirm all Task 1–6 tests pass.

### Task 7: The JSON CLI (main) — the verified interface the skill shells (FR-1 plumbing, UFR-3)

Add tests that drive `main()` like `test_preflight.py`'s style but through argv + captured stdout,
or call the pure functions the CLI delegates to. Assert the three verbs and the exit-code contract:

```python
import io, json, contextlib

def _run_cli(argv):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = preflight_readout.main(argv)
    return code, buf.getvalue()

def test_cli_assemble_emits_snapshot_json_exit_0_even_when_degraded(tmp_path):
    # a real assemble over an empty root degrades fields but must still exit 0 with a snapshot
    code, out = _run_cli(["assemble", "--work-item", "wi", "--root", str(tmp_path)])
    obj = json.loads(out)
    assert code == 0
    assert "phases" in obj  # a snapshot, not a total-failure sentinel

def test_cli_validate_override_emits_verdict():
    code, out = _run_cli(["validate-override", "--role", "reviewer",
                          "--field", "engine", "--value", "gpt"])
    obj = json.loads(out)
    assert obj["ok"] is False and "acceptedValues" in obj
```

Implement `main(argv)` in `preflight_readout.py`, mirroring `preflight.py`'s JSON CLI. `assemble`
exits 0 with a snapshot even when `degraded` is non-empty; a non-zero exit + reason only for a total
assembly failure (`ok:false`):

```python
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
```

Run the pytest file; confirm all Task 1–7 tests pass.

### Task 8: run_overrides — the durable per-run seam (FR-13)

Create `plugins/superheroes/lib/tests/test_run_overrides.py` first:

```python
import os, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import run_overrides

def test_write_then_read_roundtrips(tmp_path, monkeypatch):
    # pin the control-plane store under tmp so the test never touches the real store
    monkeypatch.setenv("SUPERHEROES_STORE_ROOT", str(tmp_path / "store"))
    root = str(tmp_path / "repo")
    os.makedirs(root, exist_ok=True)
    ov = {"reviewer": {"engine": "codex"}}
    snap = {"workItem": "wi", "phases": [], "version": 1}
    run_overrides.write("wi", root, ov, snap)
    got = run_overrides.read("wi", root)
    assert got["overrides"] == ov
    assert got["frozenSnapshot"]["workItem"] == "wi"

def test_read_absent_fails_open_to_no_overrides(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPERHEROES_STORE_ROOT", str(tmp_path / "store"))
    root = str(tmp_path / "repo")
    os.makedirs(root, exist_ok=True)
    got = run_overrides.read("wi-none", root)
    assert got["overrides"] == {} and got["frozenSnapshot"] is None

def test_read_corrupt_fails_open(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPERHEROES_STORE_ROOT", str(tmp_path / "store"))
    root = str(tmp_path / "repo")
    os.makedirs(root, exist_ok=True)
    # write a garbage record at the expected path, then confirm read fails open
    run_overrides.write("wi", root, {"reviewer": {"engine": "codex"}}, {"version": 1})
    path = run_overrides._record_path("wi", root)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("{not json")
    got = run_overrides.read("wi", root)
    assert got["overrides"] == {} and got["frozenSnapshot"] is None
```

Implement `plugins/superheroes/lib/run_overrides.py`, riding the control-plane store the run's
journal/checkpoint already use. Fail-open on an unreadable/older record (a cost/UX concern, never a
correctness one — the run still resolves each phase through the live resolvers):

```python
"""Durable per-run dispatch overrides + the frozen preflight-readout snapshot (spec FR-13/FR-14).
Persists to the control-plane run record (the substrate the run's journal/checkpoint/resume use),
so an override outlives one launch and is reapplied on relaunch. Fail-OPEN on an unreadable/older
record -> {overrides:{}, frozenSnapshot:None}: a lost/garbled override is a cost concern, never a
correctness one (the run still resolves each phase through the live resolvers). stdlib only."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import control_plane

SCHEMA_VERSION = 1
_FILENAME = "run-overrides.json"


def _record_path(work_item, root, cwd=None):
    cwd = cwd if cwd is not None else os.getcwd()
    return os.path.join(control_plane.issue_dir(cwd, work_item, root), _FILENAME)


def write(work_item, root, overrides, frozen_snapshot, cwd=None):
    """Persist the accepted overrides + the frozen snapshot atomically. Returns True on success."""
    cwd = cwd if cwd is not None else os.getcwd()
    control_plane.ensure_store(cwd, root)
    path = _record_path(work_item, root, cwd)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    rec = {"schemaVersion": SCHEMA_VERSION,
           "overrides": overrides if isinstance(overrides, dict) else {},
           "frozenSnapshot": frozen_snapshot}
    try:
        control_plane.atomic_write(path, json.dumps(rec, indent=2))
        return True
    except OSError:
        return False


def read(work_item, root, cwd=None):
    """Return {overrides, frozenSnapshot}. Fail-open to {overrides:{}, frozenSnapshot:None} on an
    absent, unreadable, corrupt, or newer-schema record (never raises)."""
    empty = {"overrides": {}, "frozenSnapshot": None}
    try:
        path = _record_path(work_item, root, cwd)
        with open(path, encoding="utf-8") as fh:
            rec = json.load(fh)
    except (OSError, ValueError):
        return empty
    if not isinstance(rec, dict):
        return empty
    if rec.get("schemaVersion", SCHEMA_VERSION) != SCHEMA_VERSION:
        return empty  # older/newer shape -> fail open (FR-14 re-validation still surfaces stale-but-readable)
    ov = rec.get("overrides")
    return {"overrides": ov if isinstance(ov, dict) else {},
            "frozenSnapshot": rec.get("frozenSnapshot")}
```

Run `python3 -m pytest plugins/superheroes/lib/tests/test_run_overrides.py -q`; confirm the three
tests pass.

### Task 9: Spine — thread the frozen snapshot into dispatch (FR-8, UFR-2 second clause)

Add a Node smoke `plugins/superheroes/lib/tests/showrunner_preflight_freeze_smoke.js` that asserts a
pinned snapshot value is what the twins resolve, and that an unpinned (absent) field resolves live.
Follow the existing smoke structure (`showrunner_startup_fold_smoke.js` is the closest analog for
exercising the startup globals). Assert against the twins directly, seeding the globals as the
startup pipe will:

```javascript
const assert = require('assert')
const modelTier = require('../model_tier.js')
const enginePref = require('../engine_pref.js')

async function main() {
  // FR-8: a pinned per-role model in __SR_OVERRIDES is what resolveModel returns (the frozen value).
  globalThis.__SR_OVERRIDES = { author: 'sonnet' }  // seeded by the startup pipe from the frozen snapshot
  assert.strictEqual(modelTier.resolveModel('author', globalThis.__SR_OVERRIDES, null), 'sonnet')

  // UFR-2: an unpinned field (absent from the frozen overrides) resolves live to the band default.
  globalThis.__SR_OVERRIDES = {}
  assert.strictEqual(modelTier.resolveModel('author', globalThis.__SR_OVERRIDES, null), 'opus')

  // FR-8/FR-12: a pinned engine pref is what resolveEngine returns.
  globalThis.__SR_ENGINE_PREFS = { reviewer: 'codex', implementation: 'claude', effort: { review: 'xhigh' } }
  assert.strictEqual(enginePref.resolveEngine('review', globalThis.__SR_ENGINE_PREFS), 'codex')
  assert.strictEqual(enginePref.resolveEffort('codex', 'review', globalThis.__SR_ENGINE_PREFS.effort), 'xhigh')

  console.log('showrunner_preflight_freeze_smoke ok')
}
main().catch((e) => { console.error(e); process.exit(1) })
```

Then wire the spine in `plugins/superheroes/lib/showrunner.js`. In the `showrunner()` startup pipe —
where `__SR_OVERRIDES` and `__SR_ENGINE_PREFS` are already planted from `startupFacts` immediately
after the `readStartupState(workItem)` call (on main, `__SR_OVERRIDES` at ~lines 1486–1489 and
`__SR_ENGINE_PREFS` at ~line 1516; grep for `globalThis.__SR_OVERRIDES =` / `globalThis.__SR_ENGINE_PREFS =`
in `showrunner()` to anchor the exact site rather than trusting the numbers, which drift) — read the
frozen snapshot for this work-item and, when present, derive the pinned
per-role model/engine/effort maps from it and merge them over the config-derived maps so the
frozen value wins. The merge is additive: a role the snapshot pins overrides the config-derived
value; a role the snapshot left unavailable (no pin) keeps the config-derived resolve-live value.
Add a helper that reads the record via a courier exec of `run_overrides.read` (the record is on the
control-plane store, off the sandbox), following the `readStartupState` pattern; fold it into the
same startup gather so no new startup leaf is added (respect the #118 two-leaf startup budget — the
freeze read piggybacks the existing `read startup state` gather). Keep the resolvers byte-unchanged;
the only spine change is seeding the globals from the frozen snapshot ahead of the config-derived
seed.

Run the node smoke via `node plugins/superheroes/lib/tests/showrunner_preflight_freeze_smoke.js` and
confirm it prints `ok`; then run the full node smoke suite through the pytest wrapper (Task 13).

### Task 10: Roster-parity node smoke — the readout roster equals the spine's PHASES (Risk: roster drift)

Add `plugins/superheroes/lib/tests/showrunner_preflight_roster_smoke.js` asserting that
`preflight_readout.PHASES` equals `showrunner.js`'s exported `PHASES`, so a phase add in the spine
fails a test rather than silently under-reporting in the readout. Shell the Python side for its
roster and compare:

```javascript
const assert = require('assert')
const { execFileSync } = require('child_process')
const path = require('path')
const showrunner = require('../showrunner.js')

function main() {
  const libDir = path.join(__dirname, '..')
  const out = execFileSync('python3', ['-c',
    'import sys; sys.path.insert(0, sys.argv[1]); import preflight_readout, json; ' +
    'print(json.dumps(list(preflight_readout.PHASES)))', libDir], { encoding: 'utf8' })
  const pyPhases = JSON.parse(out)
  assert.deepStrictEqual(pyPhases, showrunner.PHASES,
    'preflight_readout.PHASES must equal showrunner.js PHASES (roster-drift guard)')
  console.log('showrunner_preflight_roster_smoke ok')
}
main()
```

Run it with `node`; confirm `ok`.

### Task 11: SKILL step 1.5 — the interactive confirm/override loop (FR-1, FR-9, FR-10, FR-11, UFR-1)

Edit `plugins/superheroes/skills/showrunner/SKILL.md`. Insert a new **step 1.5** between the current
step 1 (Pre-flight gate) and step 2 (Launch the bundle). Renumber the launch to step 2 and readout
to step 3 remain as-is (they already are 2 and 3). The new step narrates host-neutral actions (the
file already resolves them via the host tool map), reusing the existing "the skill carries the
interactive touchpoint" pattern:

- Shell `preflight_readout.py assemble --work-item "<work-item>" --root "$ROOT"` and parse the
  snapshot JSON. On a total-failure sentinel (`ok:false`), print `reason` + `remediation` and
  **STOP** — do not launch (UFR-3, fail-closed, matching the pre-flight gate's posture).
- Shell `preflight_readout.py render --snapshot '<snapshot-json>'` and print the readout verbatim
  (or render in-process via a heredoc, like the run-end readout already does in step 3).
- Loop on the host ask primitive (`AskUserQuestion` on Claude; resolve per the host tool map):
  - **Confirm** → shell `run_overrides.write` to freeze the snapshot + persist any accepted
    overrides, then proceed to step 2 (launch). No dispatch precedes this confirm (FR-1).
  - **Override** → collect `role`, `field`, `value`; shell
    `preflight_readout.py validate-override --role … --field … --value …`. On `ok:false`, show
    `acceptedValues` + `reason`, keep the currently-effective value, and re-prompt (UFR-6). On
    `ok:true`, re-shell `assemble` with `--run-overrides` carrying the accumulated overrides,
    re-render (the overridden line marked, others unchanged, FR-11), and re-confirm.
  - **Decline** → abort the launch immediately: no `run_overrides.write`, no bundle launch, the run
    is not marked started, no branch/PR touched (UFR-1). Print a plain "aborted, no changes" line.
- Note that a relaunch/resume re-enters Start → this step re-renders with current settings +
  recorded overrides and re-confirms (FR-9/FR-14); the recorded overrides are read by `assemble`'s
  freeze read on the spine side (Task 9). Any now-invalid override is carried on its row as
  `overrideInvalid` and printed by `render` as a per-row "recorded override no longer valid, NOT
  applied ⚠" flag (FR-14 — the owner sees the flag on the affected phase line itself, not merely a
  summary line; asserted by Task 2's `test_render_shows_override_invalid_flag_on_the_row`). Likewise
  a role whose engine is unauthorized is printed with a per-row "falls back to Claude ⚠" flag
  (FR-4), asserted by Task 2's `test_render_shows_fallback_to_claude_flag_on_the_row` and Task 12.

Keep the step concise and host-neutral (no Claude-specific tool names in prose beyond the host-map
reference already established at the top of the file). Run `python3
.github/scripts/validate_skills.py` to confirm the skill still passes the token-shape validator
(line counts, description size, required phrases, CONVENTIONS citations); adjust wording only as the
validator requires — do not change the skill's front-matter `description`.

### Task 12: End-to-end assemble→render golden test + the ≤40-line bound under a full external pipeline

Add a test to `test_preflight_readout.py` that assembles over a fully-external-configured fake and
asserts the render still honors the scannability bound and shows every required element (the spec's
DoD list): every phase's engine/model/effort, external-engine authorization, provisional
calibration, verify, storage:

```python
def test_full_external_pipeline_render_within_bound_and_complete():
    readers = _fake_readers(
        prefs={"reviewer": "codex", "implementation": "cursor", "effort": {"review": "high"}},
        authz={"codex": {"installed": True, "authed": True, "error": None},
               "cursor": {"installed": True, "authed": False, "error": None}},
        calibration={"status": "provisional"}, verify="npm test",
        storage={"mode": "global", "docsPath": "/proj/docs"})
    snap = preflight_readout.assemble("wi", "/root", readers=readers)
    text = preflight_readout.render(snap)
    lines = text.splitlines()
    assert len(lines) <= 40                       # NFR scannability
    assert "provisional" in text                  # FR-5
    assert "npm test" in text                      # FR-6
    assert "global" in text and "/proj/docs" in text  # FR-7
    assert "External engines" in text              # FR-4
    # cursor unauthorized -> the affected phase ROW itself shows the fallback flag (FR-4,
    # premortem-001), not merely the External-engines summary line.
    assert "falls back to Claude" in text
    builder = [r for r in snap["phases"] if r["kind"] == "build"][0]
    assert builder.get("fallbackToClaude") is True
    # and the whole-run summary line still names the unauthorized engine
    assert "NOT authorized" in text
```

Run the pytest file; confirm the whole `test_preflight_readout.py` suite (Tasks 1–7, 12) passes.

### Task 13: Full gate — validators + pytest + node smokes green

Run the whole CI gate locally and fix any failure before handing off. From the repo root:

```bash
python3 .github/scripts/validate_marketplace.py
python3 .github/scripts/validate_hosts.py
python3 .github/scripts/validate_skills.py
python3 -m pytest .github/scripts/tests/ plugins/superheroes/lib/tests/ plugins/superheroes/eval/tests/ eval/lib/tests/ -q
```

The pytest wrapper runs the Node smoke tests (including the three new ones:
`showrunner_preflight_freeze_smoke.js`, `showrunner_preflight_roster_smoke.js`, and the roster/freeze
assertions); confirm they are picked up and green. Confirm the new modules
(`preflight_readout.py`, `run_overrides.py`) and the two new test files are present and pass, the
spine smoke suite still passes (the pin-or-resolve fork is additive and behavior-preserving when no
snapshot is present), and `validate_skills.py` passes with the edited `SKILL.md`. The task is done
when every command above exits 0.
