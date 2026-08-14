# Guardian calibration (`guardian-config`)

The guardian hero layer (`guardian.md`) holds a single machine-readable fence that tunes sweep
behavior. Write it through `core_md.py write-layer --hero guardian` (the same hero-layer machinery
`configure` uses for every optional hero). The top-level parser of record is
`guardian_sweep.read_config` — downstream modules consume its resolved output; extend that single
parser for new parsing needs, never a second parser (CONVENTIONS §11).

## Where the fence lives

In `guardian.md`, embed one fenced block tagged `guardian-config`:

````markdown
```json guardian-config
{ ... }
```
````

An **absent** layer, an **empty** layer, an **unreadable** layer (file-level I/O error), or a
layer with **no** `guardian-config` fence is **healthy** — plugin defaults are authoritative and
benching authority is retained. `core_md._layer_is_empty` catches `OSError` and treats the layer
as empty before `read_config`'s own unreadable branch can run; that branch is therefore reachable
only in a TOCTOU window. A layer file that is not valid UTF-8 raises `UnicodeDecodeError` out of
`core_md._layer_is_empty`
(it catches only `OSError`) and is not mapped to either healthy or degraded — the error
propagates. **Malformed JSON** or a fence whose parsed value is **not an object** sets
`configStatus: "degraded"`, which **revokes benching authority for that sweep** (plugin defaults
still govern thresholds and cadence on those paths). A **`reportCard` value that is present but not
an object** also sets `configStatus: "degraded"` and returns **before** `_resolve_cadence` runs, so
owner cadence is not resolved on that path (thresholds and other keys parsed earlier in
`read_config` still apply from the block) — see `guardian_ledger._resolve_thresholds`.

`cadenceTuned` is a **derived, read-only output** of `read_config` (which cadence keys the owner
positively set).

## Worked example

```json guardian-config
{
  "thresholds": {
    "complexity": 80,
    "cloneLines": 120,
    "couplingEdges": {"kind": "relative", "limit": 0.15}
  },
  "cadence": {"minMerges": 15, "minDays": 21},
  "coverage": [
    {
      "lens": "deps",
      "tool": "npm audit",
      "path": "package.json",
      "covers": ["npm"],
      "staleDays": 30
    }
  ],
  "vitals": true,
  "verifyBudgetSeconds": 300,
  "firstBaselineValidateMax": 10,
  "reportCard": {
    "actionabilityBar": 0.90,
    "minAdjudicated": 10,
    "minSweeps": 3
  }
}
```

## Keys

| Key | Type / shape | Default | What it affects |
| --- | --- | --- | --- |
| `thresholds` | Object. Red-line scalars `{"complexity": int, "cloneLines": int}` plus per-vital override entries `{"kind": …, "limit": …}` (validated by `guardian_vitals._valid_threshold_override`) | `guardian_lens.RED_LINE_THRESHOLDS` = `{"complexity": 100, "cloneLines": 100}`; per-vital overrides default from `guardian_vitals.DRIFT_THRESHOLDS` = `{"couplingEdges": {"kind": "relative", "limit": 0.25}, "duplicationPercent": {"kind": "absolute", "limit": 2.0}, "fileCount": {"kind": "relative", "limit": 0.2}, "locTotal": {"kind": "relative", "limit": 0.2}, "majorsBehind": {"kind": "absolute", "limit": 5}, "suiteRuntimeSeconds": {"kind": "relative", "limit": 0.4}, "suiteSkipped": {"kind": "any-increase"}, "suiteTestCount": {"kind": "none"}, "todoCount": {"kind": "relative", "limit": 0.25}, "vulnCount": {"kind": "any-increase"}}` | Merged at `guardian_sweep.read_config`; red lines in `guardian_lens_duplication` and `guardian_lens_hotspots`; per-vital drift thresholds in `guardian_vitals` |
| `cadence` | Object `{"minMerges": positive int, "minDays": positive int}`; non-positive or non-int entries are ignored | `CADENCE_DEFAULTS` = `{"minMerges": 10, "minDays": 14}` (`guardian_sweep.py`) | Resolved by `guardian_sweep._resolve_cadence`; displayed by `configure_view._cadence_view` |
| `coverage` | List of objects, each `{"lens": …, "tool": …, "path": …, "covers": …, "staleDays": …}`; `covers` must be a non-empty list of non-empty strings or the entry's scope is treated as unproven and nothing is suppressed | `[]` | Stored at `guardian_sweep.read_config`; `staleDays` parsed per entry in `guardian_lens_deps` |
| `vitals` / `collectVitals` | Bool; **either** key set to `false` disables vitals collection | `true` (collection on) | `guardian_sweep.read_config` → `vitalsEnabled` |
| `verifyBudgetSeconds` / `vitalsBudgetSeconds` | Positive number; when both are present, **`verifyBudgetSeconds` wins** | `_DEFAULT_VERIFY_BUDGET_SECONDS` (300) | Shared verify/vitals time budget for the sweep (`guardian_sweep.read_config`, consumed during collect/finalize) |
| `firstBaselineValidateMax` | Non-negative int | `_DEFAULT_FIRST_BASELINE_VALIDATE_MAX` (10) | Caps first-baseline candidates routed through validation (`guardian_sweep.read_config`, used during collect) |
| `reportCard` | Object `{"actionabilityBar": float, "minAdjudicated": int, "minSweeps": int}`; a **non-object** value degrades the **whole** config. `actionabilityBar` must be a finite number in `(0, 1]` (bool, NaN, and non-numeric values rejected); `minAdjudicated` and `minSweeps` must be positive non-bool ints (`guardian_ledger._resolve_thresholds`) | `guardian_ledger.REPORT_CARD_DEFAULTS` = `{"actionabilityBar": 0.90, "minAdjudicated": 10, "minSweeps": 3}` | Parsed at `guardian_sweep.read_config`; thresholds and benching in `guardian_ledger.report_card` / `_resolve_thresholds` |

## Load-bearing behaviours

**Healthy absence.** No fence (or no `guardian.md` layer at all) is not an error — defaults govern
every knob above.

**Degraded config revokes benching.** Malformed JSON or a non-object fence yields
`configStatus: "degraded"` with plugin defaults governing thresholds and cadence. A `reportCard`
value that is present but not an object also yields `configStatus: "degraded"` but returns before
owner cadence is resolved (other keys parsed earlier in the block still apply). That status
revokes benching authority for the sweep even when individual override keys look fine — defaults
must not become a silent mute button after a config typo.

**Vitals off.** Setting `vitals: false` **or** `collectVitals: false` disables vitals collection;
if both keys appear with different values, **either** being `false` wins (collection off).

**Per-role dispatch effort is elsewhere.** v2 dispatch effort comes from the registry or per-seat
pins, resolved through `dispatch_guard` / `seat_map` — not from `guardian-config`.
