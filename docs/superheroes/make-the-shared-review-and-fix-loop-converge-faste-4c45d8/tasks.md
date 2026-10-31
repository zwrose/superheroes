---
superheroes: doc
schemaVersion: 1
docType: tasks
workItem: make-the-shared-review-and-fix-loop-converge-faste-4c45d8
issue: 125
size: large
status: approved
gates: {review: passed}
producedBy: "the-architect@0.3.0"
created: "2026-07-01"
updated: "2026-07-01"
---
# Make the shared review-and-fix loop converge faster and cost less - Tasks

> **Build contract (superheroes).** These tasks are executed by the producer's **Build**
> phase - **not here**. Build invokes superpowers **subagent-driven-development** with the
> worktree **pre-verified, not created**, and **without** `finishing-a-development-branch`;
> the **producer enforces both clips** at invocation. `size: large`. Advance to Build
> only once `gates.review: passed`.

**Goal:** Make the shared review-and-fix loop converge in fewer rounds and spend fewer tokens while preserving the full-panel final confirmation safety floor.

**Architecture:** Add pure scheduling, memory, coverage-decision, and telemetry helpers with Python/JS parity where the bundled showrunner needs in-process decisions. Extend the existing `review_panel_shell.js` and deciders instead of creating per-review loops. Keep terminal decisions in `panel_tally`/`loop_state`, keep recurrence signals in `review_memory`, and keep all durable writes fenced and atomic.

**Tech Stack:** Python stdlib helpers, Node/CommonJS JS twins, existing pytest parity fixtures, existing Node smoke tests, existing skill-shape validators, no new package dependency.

---

## Global Constraints

- Work only from an isolated worktree, not `/path/to/home/superheroes`.
- Keep the repo's control-flow posture: `review_panel_shell.js` detects events and forwards state; pure deciders own decisions.
- Preserve Python/JS parity for every bundled pure helper by updating `plugins/superheroes/lib/tests/test_parity.py`, fixture directories, and `plugins/superheroes/lib/bundle_showrunner.js`.
- Never let a partial, skipped, low-confidence, malformed, stale, or corrupt review state certify as passed.
- Every task ends with the listed command and commit. Commit messages use the concrete messages shown in the task.

### Task 1: Add Schedule-Only Round Policy

**Files:**
- Create: `plugins/superheroes/lib/review_round_policy.py`
- Create: `plugins/superheroes/lib/review_round_policy.js`
- Create: `plugins/superheroes/lib/tests/parity/review_round_policy/planRound/01_baseline_all_deep.json`
- Create: `plugins/superheroes/lib/tests/parity/review_round_policy/planRound/02_intermediate_skip_clean_untouched.json`
- Create: `plugins/superheroes/lib/tests/parity/review_round_policy/planRound/03_unknown_subject_runs_all_deep.json`
- Create: `plugins/superheroes/lib/tests/parity/review_round_policy/planRound/04_confirmation_all_deep.json`
- Create: `plugins/superheroes/lib/tests/parity/review_round_policy/planRound/05_malformed_changed_subjects_runs_all_deep.json`
- Create: `plugins/superheroes/lib/tests/parity/review_round_policy/planRound/06_nonnumeric_round_runs_all_deep.json`
- Create: `plugins/superheroes/lib/tests/parity/review_round_policy/planRound/07_malformed_dimensions_safe_empty.json`
- Create: `plugins/superheroes/lib/tests/parity/review_round_policy/planRound/08_real_memory_record_shape_schedules_skip.json`
- Create: `plugins/superheroes/lib/tests/parity/review_round_policy/planRound/09_carried_blocker_runs_dimension.json`
- Modify: `plugins/superheroes/lib/tests/test_parity.py`
- Modify: `plugins/superheroes/lib/bundle_showrunner.js`

**Interfaces:**
- Produces: `plan_round(state)` / `planRound(state)` returning `{roundKind, dimensions, escalationPolicy}`.
- Consumes: prior dimension statuses, changed subjects, confirmation flag, round number.
- Does not produce: terminal verdicts or `generalizeRequired`.

- [ ] **Step 1: Write failing parity fixtures**

Create `plugins/superheroes/lib/tests/parity/review_round_policy/planRound/01_baseline_all_deep.json`:

```json
{
  "input": [{
    "round": 1,
    "dimensions": ["architecture-reviewer", "code-reviewer", "security-reviewer"],
    "changedSubjects": [],
    "previous": {},
    "confirmation": false
  }],
  "expected": {
    "roundKind": "baseline",
    "dimensions": {
      "architecture-reviewer": {"action": "run", "tier": "reviewer-deep", "reason": "baseline full-panel"},
      "code-reviewer": {"action": "run", "tier": "reviewer-deep", "reason": "baseline full-panel"},
      "security-reviewer": {"action": "run", "tier": "reviewer-deep", "reason": "baseline full-panel"}
    },
    "escalationPolicy": "deep-only"
  }
}
```

Create `02_intermediate_skip_clean_untouched.json`:

```json
{
  "input": [{
    "round": 2,
    "dimensions": ["test-reviewer", "security-reviewer"],
    "changedSubjects": ["Test"],
    "previous": {
      "test-reviewer": {"status": "run", "confidence": "high", "hasFindings": true, "subjects": ["Test"], "round": 1},
      "security-reviewer": {"status": "run", "confidence": "high", "hasFindings": false, "subjects": ["Security"], "round": 1}
    },
    "confirmation": false
  }],
  "expected": {
    "roundKind": "intermediate",
    "dimensions": {
      "test-reviewer": {"action": "run", "tier": "reviewer", "reason": "previous finding or changed subject"},
      "security-reviewer": {"action": "skip", "tier": "reviewer-deep", "reason": "high-confidence clean and untouched", "carriedFromRound": 1}
    },
    "escalationPolicy": "cheap-first"
  }
}
```

Create `03_unknown_subject_runs_all_deep.json`:

```json
{
  "input": [{
    "round": 3,
    "dimensions": ["code-reviewer", "security-reviewer"],
    "changedSubjects": null,
    "previous": {
      "code-reviewer": {"status": "run", "confidence": "high", "hasFindings": false, "subjects": ["Code"], "round": 2},
      "security-reviewer": {"status": "run", "confidence": "high", "hasFindings": false, "subjects": ["Security"], "round": 2}
    },
    "confirmation": false
  }],
  "expected": {
    "roundKind": "intermediate",
    "dimensions": {
      "code-reviewer": {"action": "run", "tier": "reviewer-deep", "reason": "unknown changed subjects"},
      "security-reviewer": {"action": "run", "tier": "reviewer-deep", "reason": "unknown changed subjects"}
    },
    "escalationPolicy": "deep-only"
  }
}
```

Create `04_confirmation_all_deep.json`:

```json
{
  "input": [{
    "round": 4,
    "dimensions": ["architecture-reviewer", "code-reviewer"],
    "changedSubjects": ["Docs"],
    "previous": {},
    "confirmation": true
  }],
  "expected": {
    "roundKind": "confirmation",
    "dimensions": {
      "architecture-reviewer": {"action": "run", "tier": "reviewer-deep", "reason": "confirmation full-panel"},
      "code-reviewer": {"action": "run", "tier": "reviewer-deep", "reason": "confirmation full-panel"}
    },
    "escalationPolicy": "deep-only"
  }
}
```

Create `05_malformed_changed_subjects_runs_all_deep.json`:

```json
{
  "input": [{
    "round": 2,
    "dimensions": ["security-reviewer", "test-reviewer"],
    "changedSubjects": "Security",
    "previous": {
      "security-reviewer": {"status": "run", "confidence": "high", "hasFindings": false, "subjects": ["Security"], "round": 1},
      "test-reviewer": {"status": "run", "confidence": "high", "hasFindings": false, "subjects": ["Test"], "round": 1}
    },
    "confirmation": false
  }],
  "expected": {
    "roundKind": "intermediate",
    "dimensions": {
      "security-reviewer": {"action": "run", "tier": "reviewer-deep", "reason": "unknown changed subjects"},
      "test-reviewer": {"action": "run", "tier": "reviewer-deep", "reason": "unknown changed subjects"}
    },
    "escalationPolicy": "deep-only"
  }
}
```

Create `06_nonnumeric_round_runs_all_deep.json`:

```json
{
  "input": [{
    "round": "corrupt",
    "dimensions": ["test-reviewer", "security-reviewer"],
    "changedSubjects": ["Test"],
    "previous": {
      "test-reviewer": {"status": "run", "confidence": "high", "findings": [{"dimension": "Test", "severity": "Important"}], "round": 1},
      "security-reviewer": {"status": "run", "confidence": "high", "findings": [], "round": 1}
    }
  }],
  "expected": {
    "roundKind": "intermediate",
    "dimensions": {
      "test-reviewer": {"action": "run", "tier": "reviewer-deep", "reason": "malformed round state"},
      "security-reviewer": {"action": "run", "tier": "reviewer-deep", "reason": "malformed round state"}
    },
    "escalationPolicy": "deep-only"
  }
}
```

Create `07_malformed_dimensions_safe_empty.json`:

```json
{
  "input": [{
    "round": 2,
    "dimensions": "test-reviewer",
    "changedSubjects": ["Test"],
    "previous": []
  }],
  "expected": {
    "roundKind": "intermediate",
    "dimensions": {},
    "escalationPolicy": "cheap-first"
  }
}
```

Create `08_real_memory_record_shape_schedules_skip.json`:

```json
{
  "input": [{
    "round": 2,
    "dimensions": ["test-reviewer", "security-reviewer"],
    "changedSubjects": ["Test"],
    "previous": {
      "test-reviewer": {"dimension": "test-reviewer", "status": "run", "confidence": "high", "findings": [{"dimension": "Test", "taxonomy": "coverage", "title": "Missing acceptance test", "severity": "Important"}], "round": 1},
      "security-reviewer": {"dimension": "security-reviewer", "status": "run", "confidence": "high", "findings": [], "round": 1}
    }
  }],
  "expected": {
    "roundKind": "intermediate",
    "dimensions": {
      "test-reviewer": {"action": "run", "tier": "reviewer", "reason": "previous finding or changed subject"},
      "security-reviewer": {"action": "skip", "tier": "reviewer-deep", "reason": "high-confidence clean and untouched", "carriedFromRound": 1}
    },
    "escalationPolicy": "cheap-first"
  }
}
```

Create `09_carried_blocker_runs_dimension.json`:

```json
{
  "input": [{
    "round": 3,
    "dimensions": ["security-reviewer", "test-reviewer"],
    "changedSubjects": ["Test"],
    "previous": {
      "security-reviewer": {"dimension": "Security", "status": "skipped", "confidence": "high", "findings": [{"dimension": "Security", "taxonomy": "leak", "title": "Secret leaked", "severity": "Important", "carried": true, "sourceRound": 1}], "currentFindings": [], "carriedFindings": [{"dimension": "Security", "taxonomy": "leak", "title": "Secret leaked", "severity": "Important", "carried": true, "sourceRound": 1}], "hasFindings": true, "subjects": ["Security"], "round": 2, "carriedFromRound": 1},
      "test-reviewer": {"dimension": "Test", "status": "run", "confidence": "high", "findings": [], "hasFindings": false, "subjects": ["Test"], "round": 2}
    }
  }],
  "expected": {
    "roundKind": "intermediate",
    "dimensions": {
      "security-reviewer": {"action": "run", "tier": "reviewer", "reason": "previous finding or changed subject"},
      "test-reviewer": {"action": "run", "tier": "reviewer", "reason": "previous finding or changed subject"}
    },
    "escalationPolicy": "cheap-first"
  }
}
```

- [ ] **Step 2: Run the targeted failing test**

Run: `python3 -m pytest plugins/superheroes/lib/tests/test_parity.py -q`

Expected: FAIL with missing fixture directory or missing `review_round_policy` registration.

- [ ] **Step 3: Add the Python helper**

Create `plugins/superheroes/lib/review_round_policy.py`:

```python
#!/usr/bin/env python3
"""Schedule-only round policy for the shared review loop.

This helper never decides loop terminals and never computes recurrence. It only decides
round kind, reviewer run/skip choices, tiers, and cheap-result escalation policy.
"""

DEEP = "reviewer-deep"
CHEAP = "reviewer"


def _dim(prev, name):
    return prev.get(name, {}) if isinstance(prev, dict) else {}


def _changed_subjects(value):
    if not isinstance(value, list) or any(not isinstance(x, str) for x in value):
        return None
    return value


def _safe_round(value):
    try:
        return int(value or 1), False
    except (TypeError, ValueError):
        return 1, True


def _subjects(name, info):
    if isinstance(info.get("subjects"), list):
        return [s for s in info.get("subjects") if isinstance(s, str)]
    subjects = []
    for finding in info.get("findings") or []:
        if isinstance(finding, dict) and isinstance(finding.get("dimension"), str):
            subjects.append(finding["dimension"])
    prefix = str(name or "").split("-")[0].lower()
    fallback = {"test": "Test", "security": "Security", "code": "Code", "architecture": "Architecture", "failure": "Failure-Mode"}.get(prefix)
    if fallback:
        subjects.append(fallback)
    return sorted(set(subjects))


def _has_findings(info):
    findings = info.get("findings")
    current = info.get("currentFindings")
    carried = info.get("carriedFindings")
    for value in (findings, current, carried):
        if isinstance(value, list) and len(value) > 0:
            return True
    if isinstance(info.get("hasFindings"), bool):
        return info["hasFindings"]
    if isinstance(findings, list):
        return len(findings) > 0
    return None


def _subject_touched(name, info, changed_subjects):
    if changed_subjects is None:
        return None
    subjects = _subjects(name, info)
    return bool(set(subjects) & set(changed_subjects))


def plan_round(state):
    state = state or {}
    dimensions = list(state.get("dimensions") or []) if isinstance(state.get("dimensions") or [], list) else []
    previous = state.get("previous") if isinstance(state.get("previous"), dict) else {}
    changed_subjects = _changed_subjects(state.get("changedSubjects"))
    confirmation = bool(state.get("confirmation"))
    round_no, malformed_round = _safe_round(state.get("round"))

    if malformed_round:
        return {
            "roundKind": "intermediate",
            "dimensions": {d: {"action": "run", "tier": DEEP, "reason": "malformed round state"} for d in dimensions},
            "escalationPolicy": "deep-only",
        }

    if confirmation:
        return {
            "roundKind": "confirmation",
            "dimensions": {d: {"action": "run", "tier": DEEP, "reason": "confirmation full-panel"} for d in dimensions},
            "escalationPolicy": "deep-only",
        }

    if round_no <= 1:
        return {
            "roundKind": "baseline",
            "dimensions": {d: {"action": "run", "tier": DEEP, "reason": "baseline full-panel"} for d in dimensions},
            "escalationPolicy": "deep-only",
        }

    if changed_subjects is None:
        return {
            "roundKind": "intermediate",
            "dimensions": {d: {"action": "run", "tier": DEEP, "reason": "unknown changed subjects"} for d in dimensions},
            "escalationPolicy": "deep-only",
        }

    out = {}
    for name in dimensions:
        info = _dim(previous, name)
        touched = _subject_touched(name, info, changed_subjects)
        has_findings = _has_findings(info)
        if has_findings is True or touched:
            out[name] = {"action": "run", "tier": CHEAP, "reason": "previous finding or changed subject"}
        elif info.get("confidence") == "high" and has_findings is False:
            out[name] = {
                "action": "skip",
                "tier": DEEP,
                "reason": "high-confidence clean and untouched",
                "carriedFromRound": info.get("round"),
            }
        else:
            out[name] = {"action": "run", "tier": DEEP, "reason": "not skip eligible"}
    return {"roundKind": "intermediate", "dimensions": out, "escalationPolicy": "cheap-first"}
```

- [ ] **Step 4: Add the JS twin**

Create `plugins/superheroes/lib/review_round_policy.js`:

```js
// plugins/superheroes/lib/review_round_policy.js
const DEEP = 'reviewer-deep'
const CHEAP = 'reviewer'

function _dim(prev, name) {
  return prev && typeof prev === 'object' ? (prev[name] || {}) : {}
}

function _changedSubjects(value) {
  return Array.isArray(value) && value.every((x) => typeof x === 'string') ? value : null
}

function _safeRound(value) {
  const n = Number(value || 1)
  return Number.isFinite(n) ? { value: n, malformed: false } : { value: 1, malformed: true }
}

function _subjects(name, info) {
  if (Array.isArray(info.subjects)) return info.subjects.filter((s) => typeof s === 'string')
  const subjects = []
  for (const finding of Array.isArray(info.findings) ? info.findings : []) {
    if (finding && typeof finding.dimension === 'string') subjects.push(finding.dimension)
  }
  const fallback = { test: 'Test', security: 'Security', code: 'Code', architecture: 'Architecture', failure: 'Failure-Mode' }[String(name || '').split('-')[0].toLowerCase()]
  if (fallback) subjects.push(fallback)
  return Array.from(new Set(subjects))
}

function _hasFindings(info) {
  for (const value of [info.findings, info.currentFindings, info.carriedFindings]) {
    if (Array.isArray(value) && value.length > 0) return true
  }
  if (typeof info.hasFindings === 'boolean') return info.hasFindings
  if (Array.isArray(info.findings)) return info.findings.length > 0
  return null
}

function _subjectTouched(name, info, changedSubjects) {
  if (changedSubjects === null || changedSubjects === undefined) return null
  const subjects = _subjects(name, info)
  return subjects.some((s) => changedSubjects.includes(s))
}

function planRound(state) {
  state = state || {}
  const dimensions = Array.isArray(state.dimensions) ? state.dimensions : []
  const previous = state.previous && typeof state.previous === 'object' && !Array.isArray(state.previous) ? state.previous : {}
  const changedSubjects = _changedSubjects(state.changedSubjects)
  const parsedRound = _safeRound(state.round)
  const roundNo = parsedRound.value

  if (parsedRound.malformed) {
    const out = {}
    for (const d of dimensions) out[d] = { action: 'run', tier: DEEP, reason: 'malformed round state' }
    return { roundKind: 'intermediate', dimensions: out, escalationPolicy: 'deep-only' }
  }

  if (state.confirmation) {
    const out = {}
    for (const d of dimensions) out[d] = { action: 'run', tier: DEEP, reason: 'confirmation full-panel' }
    return { roundKind: 'confirmation', dimensions: out, escalationPolicy: 'deep-only' }
  }
  if (roundNo <= 1) {
    const out = {}
    for (const d of dimensions) out[d] = { action: 'run', tier: DEEP, reason: 'baseline full-panel' }
    return { roundKind: 'baseline', dimensions: out, escalationPolicy: 'deep-only' }
  }
  if (changedSubjects === null || changedSubjects === undefined) {
    const out = {}
    for (const d of dimensions) out[d] = { action: 'run', tier: DEEP, reason: 'unknown changed subjects' }
    return { roundKind: 'intermediate', dimensions: out, escalationPolicy: 'deep-only' }
  }

  const out = {}
  for (const name of dimensions) {
    const info = _dim(previous, name)
    const touched = _subjectTouched(name, info, changedSubjects)
    const hasFindings = _hasFindings(info)
    if (hasFindings === true || touched) {
      out[name] = { action: 'run', tier: CHEAP, reason: 'previous finding or changed subject' }
    } else if (info.confidence === 'high' && hasFindings === false) {
      out[name] = { action: 'skip', tier: DEEP, reason: 'high-confidence clean and untouched', carriedFromRound: info.round }
    } else {
      out[name] = { action: 'run', tier: DEEP, reason: 'not skip eligible' }
    }
  }
  return { roundKind: 'intermediate', dimensions: out, escalationPolicy: 'cheap-first' }
}

module.exports = { planRound }
```

- [ ] **Step 5: Register parity and bundle**

In `plugins/superheroes/lib/tests/test_parity.py`, add:

```python
PARITY_TWINS.append(("review_round_policy", "planRound", "review_round_policy", "plan_round"))
PARITY_TARGET_MODULES.append("review_round_policy")
```

Insert `review_round_policy.js` before `review_panel_shell.js` in `plugins/superheroes/lib/bundle_showrunner.js`:

```js
const MODULES = ['circuit_breaker.js', 'loop_state.js', 'loop_synthesis.js', 'panel_tally.js',
                 'review_round_policy.js',
                 'ci_status.js', 'verify_gate.js',
                 'review_panel_shell.js', 'test_pilot_phase.js', 'build_progress.js',
                 'worker_recovery.js', 'task_review.js', 'build_phase.js',
                 'model_tier.js', 'phase_step.js', 'recover.js', 'front_half.js', 'showrunner.js']
```

- [ ] **Step 6: Run tests and commit**

Run: `python3 -m pytest plugins/superheroes/lib/tests/test_parity.py -q`

Expected: PASS.

Commit:

```bash
git add plugins/superheroes/lib/review_round_policy.py plugins/superheroes/lib/review_round_policy.js plugins/superheroes/lib/tests/parity/review_round_policy plugins/superheroes/lib/tests/test_parity.py plugins/superheroes/lib/bundle_showrunner.js
git commit -m "feat(superheroes): add review round scheduling policy"
```

### Task 2: Add Review Memory and Recurrence Signals

**Files:**
- Create: `plugins/superheroes/lib/review_memory.py`
- Create: `plugins/superheroes/lib/review_memory.js`
- Create: `plugins/superheroes/lib/tests/test_review_memory.py`
- Create: `plugins/superheroes/lib/tests/parity/review_memory/classKey/01_taxonomy_title.json`
- Create: `plugins/superheroes/lib/tests/parity/review_memory/recurrentClasses/01_first_occurrence_no_signal.json`
- Create: `plugins/superheroes/lib/tests/parity/review_memory/recurrentClasses/02_second_round_signals.json`
- Create: `plugins/superheroes/lib/tests/parity/review_memory/recurrentClasses/03_carried_blocker_is_not_fresh_recurrence.json`
- Create: `plugins/superheroes/lib/tests/parity/review_memory/promoteRecord/01_v1_promotes_unknown.json`
- Create: `plugins/superheroes/lib/tests/parity/review_memory/recordFromDimensionResults/01_v2_record_contains_dimensions.json`
- Create: `plugins/superheroes/lib/tests/parity/review_memory/recordFromDimensionResults/02_skipped_blocker_is_carried_not_current.json`
- Create: `plugins/superheroes/lib/tests/parity/circuit_breaker/checkCircuitBreaker/recurrence_with_unattempted_principle_progressing.json`
- Create: `plugins/superheroes/lib/tests/parity/circuit_breaker/checkCircuitBreaker/recurrence_after_challenged_principle_halts.json`
- Modify: `plugins/superheroes/lib/circuit_breaker.py`
- Modify: `plugins/superheroes/lib/circuit_breaker.js`
- Modify: `plugins/superheroes/lib/tests/test_parity.py`
- Modify: `plugins/superheroes/lib/bundle_showrunner.js`

**Interfaces:**
- Produces: `class_key`, `recurrent_classes`, `promote_record`, `record_from_dimension_results`, `load_records`, `persist_record`, JS twins `classKey`, `recurrentClasses`, `promoteRecord`, `recordFromDimensionResults`.
- Consumes: compiled findings and coverage decisions.

- [ ] **Step 1: Write failing fixtures**

Create `classKey/01_taxonomy_title.json`:

```json
{
  "input": [{"dimension": "Test", "taxonomy": "coverage", "title": "Missing acceptance test"}],
  "expected": "Test::coverage::missing acceptance test"
}
```

Create `recurrentClasses/01_first_occurrence_no_signal.json`:

```json
{
  "input": [[{"round": 1, "findings": [{"dimension": "Test", "taxonomy": "coverage", "title": "Missing acceptance test", "severity": "Important"}]}], []],
  "expected": []
}
```

Create `recurrentClasses/02_second_round_signals.json`:

```json
{
  "input": [[
    {"round": 1, "findings": [{"dimension": "Test", "taxonomy": "coverage", "title": "Missing acceptance test", "severity": "Important"}]},
    {"round": 2, "findings": [{"dimension": "Test", "taxonomy": "coverage", "title": "Missing acceptance test", "severity": "Important"}]}
  ], []],
  "expected": [{"classKey": "Test::coverage::missing acceptance test", "rounds": [1, 2]}]
}
```

Create `recurrentClasses/03_carried_blocker_is_not_fresh_recurrence.json`:

```json
{
  "input": [[
    {"round": 1, "findings": [{"dimension": "Security", "taxonomy": "leak", "title": "Secret leaked", "severity": "Important"}]},
    {"round": 2, "findings": [{"dimension": "Security", "taxonomy": "leak", "title": "Secret leaked", "severity": "Important", "carried": true, "sourceRound": 1}]}
  ], []],
  "expected": []
}
```

Create `promoteRecord/01_v1_promotes_unknown.json`:

```json
{
  "input": [{"round": 1, "findings": []}, ["code-reviewer", "security-reviewer"]],
  "expected": {
    "schemaVersion": 2,
    "round": 1,
    "kind": "unknown",
    "dimensions": {
      "code-reviewer": {"dimension": "code-reviewer", "status": "unknown"},
      "security-reviewer": {"dimension": "security-reviewer", "status": "unknown"}
    },
    "findings": [],
    "changedSubjects": null,
    "coverageDecisions": [],
    "tokenUsage": {"available": false, "reason": "promoted from schema v1"},
    "confirmationPending": false
  }
}
```

Create `recordFromDimensionResults/01_v2_record_contains_dimensions.json`:

```json
{
  "input": [2, "intermediate", {
    "test-reviewer": {"status": "run", "dimension": "Test", "confidence": "high", "findings": []},
    "security-reviewer": {"status": "skipped", "dimension": "Security", "confidence": "high", "findings": [], "carriedFromRound": 1}
  }, ["Test"], [{"id": "RCD-1", "classKey": "Test::coverage::missing"}], {"complete": true}],
  "expected": {
    "schemaVersion": 2,
    "round": 2,
    "kind": "intermediate",
    "dimensions": {
      "test-reviewer": {"status": "run", "dimension": "Test", "confidence": "high", "findings": [], "round": 2, "currentFindings": [], "carriedFindings": [], "hasFindings": false, "subjects": ["Test"]},
      "security-reviewer": {"status": "skipped", "dimension": "Security", "confidence": "high", "findings": [], "carriedFromRound": 1, "round": 2, "currentFindings": [], "carriedFindings": [], "hasFindings": false, "subjects": ["Security"]}
    },
    "findings": [],
    "carriedFindings": [],
    "changedSubjects": ["Test"],
    "coverageDecisions": [{"id": "RCD-1", "classKey": "Test::coverage::missing"}],
    "tokenUsage": {"complete": true},
    "confirmationPending": false
  }
}
```

Create `recordFromDimensionResults/02_skipped_blocker_is_carried_not_current.json`:

```json
{
  "input": [2, "intermediate", {
    "security-reviewer": {"status": "skipped", "dimension": "Security", "confidence": "high", "findings": [{"dimension": "Security", "taxonomy": "leak", "title": "Secret leaked", "severity": "Important"}], "carriedFromRound": 1}
  }, ["Test"], [], {"complete": true}],
  "expected": {
    "schemaVersion": 2,
    "round": 2,
    "kind": "intermediate",
    "dimensions": {
      "security-reviewer": {"status": "skipped", "dimension": "Security", "confidence": "high", "findings": [{"dimension": "Security", "taxonomy": "leak", "title": "Secret leaked", "severity": "Important", "carried": true, "sourceRound": 1}], "carriedFromRound": 1, "round": 2, "currentFindings": [], "carriedFindings": [{"dimension": "Security", "taxonomy": "leak", "title": "Secret leaked", "severity": "Important", "carried": true, "sourceRound": 1}], "hasFindings": true, "subjects": ["Security"]}
    },
    "findings": [],
    "carriedFindings": [{"dimension": "Security", "taxonomy": "leak", "title": "Secret leaked", "severity": "Important", "carried": true, "sourceRound": 1}],
    "changedSubjects": ["Test"],
    "coverageDecisions": [],
    "tokenUsage": {"complete": true},
    "confirmationPending": false
  }
}
```

Create `plugins/superheroes/lib/tests/test_review_memory.py`:

```python
import importlib.util
import json
import os

LIB = os.path.join(os.path.dirname(__file__), "..")


def load_memory():
    spec = importlib.util.spec_from_file_location("review_memory", os.path.join(LIB, "review_memory.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_corrupt_round_records_report_corrupt(tmp_path):
    rm = load_memory()
    path = tmp_path / "round-records.json"
    path.write_text("{corrupt", encoding="utf-8")
    state = rm.load_records_state(str(path), ["test-reviewer"])
    assert state["ok"] is False
    assert state["state"] == "corrupt"


def test_stale_round_record_write_leaves_file_unchanged(tmp_path):
    rm = load_memory()
    path = tmp_path / "round-records.json"
    path.write_text("[]\n", encoding="utf-8")
    result = rm.persist_record(str(path), [], {"round": 1, "schemaVersion": 2}, expected_hash="wrong", run_id="run-new")
    assert result == {"ok": False, "reason": "stale"}
    assert json.loads(path.read_text(encoding="utf-8")) == []


def test_carried_findings_do_not_recur():
    rm = load_memory()
    records = [
        {"round": 1, "findings": [{"dimension": "Security", "taxonomy": "leak", "title": "Secret leaked", "severity": "Important"}]},
        {"round": 2, "findings": [{"dimension": "Security", "taxonomy": "leak", "title": "Secret leaked", "severity": "Important", "carried": True}]},
    ]
    assert rm.recurrent_classes(records) == []
```

Create `plugins/superheroes/lib/tests/parity/circuit_breaker/checkCircuitBreaker/recurrence_with_unattempted_principle_progressing.json`:

```json
{
  "input": [[
    {"round": 1, "findings": [{"file": "a.py", "title": "Missing acceptance test", "severity": "Important", "classKey": "Test::coverage::missing"}]},
    {"round": 2, "findings": [{"file": "b.py", "title": "Missing acceptance test", "severity": "Important", "classKey": "Test::coverage::missing"}], "generalizeRequired": [{"classKey": "Test::coverage::missing"}]}
  ], 7],
  "expected": {"halt": false, "reason": null, "detail": "recurrence pending coverage decision"}
}
```

Create `plugins/superheroes/lib/tests/parity/circuit_breaker/checkCircuitBreaker/recurrence_after_challenged_principle_halts.json`:

```json
{
  "input": [[
    {"round": 1, "findings": [{"file": "a.py", "title": "Missing acceptance test", "severity": "Important", "classKey": "Test::coverage::missing"}]},
    {"round": 2, "findings": [{"file": "b.py", "title": "Coverage decision is false", "severity": "Important", "classKey": "Test::coverage::missing"}], "coverageDecisions": [{"classKey": "Test::coverage::missing", "challengedBy": "test-reviewer"}]}
  ], 7],
  "expected": {"halt": true, "reason": "challenged-principle-recurring", "detail": "1 challenged coverage decision class recurred after being recorded: Test::coverage::missing"}
}
```

- [ ] **Step 2: Run the failing parity test**

Run: `python3 -m pytest plugins/superheroes/lib/tests/test_parity.py -q`

Expected: FAIL for unregistered `review_memory` helpers.

- [ ] **Step 3: Add Python memory helper**

Create `plugins/superheroes/lib/review_memory.py`:

```python
#!/usr/bin/env python3
"""Pure memory helpers for review-loop recurrence and v2 round records."""
import re
import argparse
import hashlib
import json
import os
import tempfile

BLOCKING = {"Critical", "Important"}
_WS = re.compile(r"\s+")


def _norm(value):
    return _WS.sub(" ", str(value or "").strip().lower())


def content_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def class_key(finding):
    return "::".join([
        str(finding.get("dimension") or ""),
        str(finding.get("taxonomy") or ""),
        _norm(finding.get("title")),
    ])


def recurrent_classes(records, coverage_decisions=None):
    covered = {d.get("classKey") for d in (coverage_decisions or []) if isinstance(d, dict)}
    seen = {}
    for rec in records or []:
        rnd = rec.get("round")
        for finding in rec.get("findings") or []:
            if finding.get("carried"):
                continue
            if finding.get("severity") not in BLOCKING:
                continue
            key = finding.get("classKey") or class_key(finding)
            if key in covered:
                continue
            seen.setdefault(key, set()).add(rnd)
    out = []
    for key, rounds in sorted(seen.items()):
        if len(rounds) >= 2:
            out.append({"classKey": key, "rounds": sorted(rounds)})
    return out


def promote_record(record, dimensions):
    if record.get("schemaVersion") == 2:
        return record
    return {
        "schemaVersion": 2,
        "round": record.get("round"),
        "kind": "unknown",
        "dimensions": {d: {"dimension": d, "status": "unknown"} for d in (dimensions or [])},
        "findings": record.get("findings") or [],
        "changedSubjects": None,
        "coverageDecisions": [],
        "tokenUsage": {"available": False, "reason": "promoted from schema v1"},
        "confirmationPending": False,
    }


def _subject_from_reviewer(name):
    return {
        "test": "Test",
        "security": "Security",
        "code": "Code",
        "architecture": "Architecture",
        "failure": "Failure-Mode",
    }.get(str(name or "").split("-")[0].lower())


def _dimension_record(name, result, round_no):
    out = dict(result or {})
    out.setdefault("dimension", name)
    out.setdefault("round", round_no)
    raw_findings = out.get("findings") if isinstance(out.get("findings"), list) else []
    current = []
    carried = []
    is_carried = out.get("status") == "skipped" or out.get("carriedFromRound") is not None
    for finding in raw_findings:
        if not isinstance(finding, dict):
            continue
        item = dict(finding)
        item.setdefault("dimension", out.get("dimension") or name)
        if is_carried:
            item["carried"] = True
            item["sourceRound"] = out.get("carriedFromRound") or finding.get("sourceRound") or round_no
            carried.append(item)
        else:
            current.append(item)
    subjects = {f.get("dimension") for f in current + carried if f.get("dimension")}
    fallback = _subject_from_reviewer(name)
    if fallback:
        subjects.add(fallback)
    out["findings"] = current + carried
    out["currentFindings"] = current
    out["carriedFindings"] = carried
    out["hasFindings"] = bool(current or carried)
    out["subjects"] = sorted(subjects)
    return out, current, carried


def record_from_dimension_results(round_no, kind, dimensions, changed_subjects, coverage_decisions, token_usage, confirmation_pending=False):
    findings = []
    carried_findings = []
    dimension_records = {}
    for name, result in (dimensions or {}).items():
        dim_record, current, carried = _dimension_record(name, result, round_no)
        dimension_records[name] = dim_record
        findings.extend(current)
        carried_findings.extend(carried)
    return {
        "schemaVersion": 2,
        "round": round_no,
        "kind": kind,
        "dimensions": dimension_records,
        "findings": findings,
        "carriedFindings": carried_findings,
        "changedSubjects": changed_subjects,
        "coverageDecisions": coverage_decisions or [],
        "tokenUsage": token_usage or {"available": False, "reason": "missing"},
        "confirmationPending": bool(confirmation_pending),
    }


def load_records_state(path, dimensions):
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except FileNotFoundError:
        return {"ok": True, "state": "missing", "records": [], "contentHash": content_hash("")}
    except OSError as exc:
        return {"ok": False, "state": "unreadable", "records": [], "reason": str(exc)}
    try:
        data = json.loads(text)
    except ValueError as exc:
        return {"ok": False, "state": "corrupt", "records": [], "contentHash": content_hash(text), "reason": str(exc)}
    if not isinstance(data, list):
        return {"ok": False, "state": "corrupt", "records": [], "contentHash": content_hash(text), "reason": "not a list"}
    return {"ok": True, "state": "loaded", "records": [promote_record(r, dimensions) for r in data], "contentHash": content_hash(text)}


def load_records(path, dimensions):
    return load_records_state(path, dimensions)["records"]


def persist_record(path, records, record, expected_hash=None, run_id=None, lease=None):
    state = load_records_state(path, [])
    if expected_hash and state.get("contentHash") != expected_hash:
        return {"ok": False, "reason": "stale"}
    if not state.get("ok") and expected_hash:
        return {"ok": False, "reason": state.get("state") or "unreadable"}
    directory = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp = tempfile.mkstemp(prefix=".round-records-", dir=directory, text=True)
    if run_id:
        record = dict(record)
        record["runId"] = run_id
    if lease:
        record = dict(record)
        record["lease"] = lease
    merged = [r for r in (records or []) if r.get("round") != record.get("round")]
    merged.append(record)
    merged.sort(key=lambda r: r.get("round") or 0)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(merged, fh, indent=2)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
        text = json.dumps(merged, indent=2) + "\n"
        return {"ok": True, "records": merged, "contentHash": content_hash(text)}
    except OSError as exc:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        return {"ok": False, "reason": "write-failed", "detail": str(exc)}


def main(argv=None):
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    load_p = sub.add_parser("load")
    load_p.add_argument("--path", required=True)
    load_p.add_argument("--dimensions", required=True)
    persist_p = sub.add_parser("persist")
    persist_p.add_argument("--path", required=True)
    persist_p.add_argument("--dimensions", required=True)
    persist_p.add_argument("--record-json", required=True)
    persist_p.add_argument("--expected-hash")
    persist_p.add_argument("--run-id", required=True)
    persist_p.add_argument("--lease")
    args = parser.parse_args(argv)
    dimensions = json.loads(args.dimensions)
    if args.cmd == "load":
        result = load_records_state(args.path, dimensions)
        print(json.dumps(result))
        return 0 if result.get("ok") else 1
    state = load_records_state(args.path, dimensions)
    if not state.get("ok"):
        print(json.dumps(state))
        return 1
    result = persist_record(args.path, state.get("records") or [], json.loads(args.record_json), expected_hash=args.expected_hash, run_id=args.run_id, lease=args.lease)
    print(json.dumps(result))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Add JS memory twin**

Create `plugins/superheroes/lib/review_memory.js`:

```js
// plugins/superheroes/lib/review_memory.js
const BLOCKING = new Set(['Critical', 'Important'])

function _norm(value) {
  return String(value || '').trim().toLowerCase().replace(/\s+/g, ' ')
}

function classKey(finding) {
  finding = finding || {}
  return `${finding.dimension || ''}::${finding.taxonomy || ''}::${_norm(finding.title)}`
}

function recurrentClasses(records, coverageDecisions) {
  const covered = new Set((coverageDecisions || []).map((d) => d && d.classKey).filter(Boolean))
  const seen = Object.create(null)
  for (const rec of records || []) {
    for (const finding of (rec && rec.findings) || []) {
      if (finding.carried) continue
      if (!BLOCKING.has(finding.severity)) continue
      const key = finding.classKey || classKey(finding)
      if (covered.has(key)) continue
      if (!seen[key]) seen[key] = new Set()
      seen[key].add(rec.round)
    }
  }
  return Object.keys(seen).sort()
    .filter((k) => seen[k].size >= 2)
    .map((k) => ({ classKey: k, rounds: Array.from(seen[k]).sort((a, b) => a - b) }))
}

function promoteRecord(record, dimensions) {
  record = record || {}
  if (record.schemaVersion === 2) return record
  const dims = {}
  for (const d of dimensions || []) dims[d] = { dimension: d, status: 'unknown' }
  return {
    schemaVersion: 2,
    round: record.round,
    kind: 'unknown',
    dimensions: dims,
    findings: Array.isArray(record.findings) ? record.findings : [],
    changedSubjects: null,
    coverageDecisions: [],
    tokenUsage: { available: false, reason: 'promoted from schema v1' },
    confirmationPending: false,
  }
}

function recordFromDimensionResults(roundNo, kind, dimensions, changedSubjects, coverageDecisions, tokenUsage, confirmationPending) {
  const findings = []
  const carriedFindings = []
  const dimensionRecords = {}
  const subjectFallback = { test: 'Test', security: 'Security', code: 'Code', architecture: 'Architecture', failure: 'Failure-Mode' }
  for (const [name, result] of Object.entries(dimensions || {})) {
    const out = Object.assign({ dimension: name, round: roundNo }, result || {})
    const current = []
    const carried = []
    const isCarried = out.status === 'skipped' || out.carriedFromRound !== undefined
    for (const raw of Array.isArray(out.findings) ? out.findings : []) {
      const item = Object.assign({ dimension: out.dimension || name }, raw)
      if (isCarried) {
        item.carried = true
        item.sourceRound = out.carriedFromRound || item.sourceRound || roundNo
        carried.push(item)
      } else {
        current.push(item)
      }
    }
    const subjects = new Set([...current, ...carried].map((f) => f.dimension).filter(Boolean))
    const fallback = subjectFallback[String(name || '').split('-')[0].toLowerCase()]
    if (fallback) subjects.add(fallback)
    out.findings = current.concat(carried)
    out.currentFindings = current
    out.carriedFindings = carried
    out.hasFindings = current.length + carried.length > 0
    out.subjects = Array.from(subjects).sort()
    dimensionRecords[name] = out
    findings.push(...current)
    carriedFindings.push(...carried)
  }
  return {
    schemaVersion: 2,
    round: roundNo,
    kind,
    dimensions: dimensionRecords,
    findings,
    carriedFindings,
    changedSubjects,
    coverageDecisions: coverageDecisions || [],
    tokenUsage: tokenUsage || { available: false, reason: 'missing' },
    confirmationPending: !!confirmationPending,
  }
}

module.exports = { classKey, recurrentClasses, promoteRecord, recordFromDimensionResults }
```

- [ ] **Step 5: Update circuit-breaker recurrence behavior**

In `plugins/superheroes/lib/circuit_breaker.py`, change the recurring-finding branch so an unattempted recurrence with `generalizeRequired` does not halt:

```python
    if n >= 2:
        latest_rec = rounds[n - 1]
        latest_generalize = {g.get("classKey") for g in latest_rec.get("generalizeRequired", []) if isinstance(g, dict)}
        challenged = {d.get("classKey") for d in latest_rec.get("coverageDecisions", []) if isinstance(d, dict) and d.get("challengedBy")}
        latest_blocking = _blocking(latest_rec)
        prev_ids = {f.get("classKey") or finding_identity(f) for f in _blocking(rounds[n - 2])}
        recurring = [f for f in latest_blocking if (f.get("classKey") or finding_identity(f)) in prev_ids]
        challenged_recurring = [f for f in recurring if (f.get("classKey") or finding_identity(f)) in challenged]
        if challenged_recurring:
            ids = "; ".join((f.get("classKey") or finding_identity(f)) for f in challenged_recurring)
            return {"halt": True, "reason": "challenged-principle-recurring", "detail": f"{len(challenged_recurring)} challenged coverage decision class recurred after being recorded: {ids}"}
        if recurring:
            keys = {(f.get("classKey") or finding_identity(f)) for f in recurring}
            if keys & latest_generalize:
                return {"halt": False, "reason": None, "detail": "recurrence pending coverage decision"}
            ids = "; ".join(sorted(keys))
            return {"halt": True, "reason": "recurring-finding", "detail": f"{len(recurring)} blocking finding(s) recurred after a fix was committed: {ids}"}
```

Make the matching change in `plugins/superheroes/lib/circuit_breaker.js` using the same field names and expected outputs.

- [ ] **Step 6: Register parity and bundle**

Add to `PARITY_TWINS`:

```python
("review_memory", "classKey", "review_memory", "class_key"),
("review_memory", "recurrentClasses", "review_memory", "recurrent_classes"),
("review_memory", "promoteRecord", "review_memory", "promote_record"),
("review_memory", "recordFromDimensionResults", "review_memory", "record_from_dimension_results"),
```

Add `review_memory` to `PARITY_TARGET_MODULES` and add `review_memory.js` to `MODULES` before `review_panel_shell.js`.

- [ ] **Step 7: Run tests and commit**

Run: `python3 -m pytest plugins/superheroes/lib/tests/test_parity.py -q`

Expected: PASS.

Commit:

```bash
git add plugins/superheroes/lib/review_memory.py plugins/superheroes/lib/review_memory.js plugins/superheroes/lib/tests/test_review_memory.py plugins/superheroes/lib/tests/parity/review_memory plugins/superheroes/lib/tests/test_parity.py plugins/superheroes/lib/bundle_showrunner.js
git commit -m "feat(superheroes): add review memory recurrence helpers"
```

### Task 3: Add Atomic Coverage Decisions

**Files:**
- Create: `plugins/superheroes/lib/coverage_decisions.py`
- Create: `plugins/superheroes/lib/tests/test_coverage_decisions.py`

**Interfaces:**
- Produces: bounded `## Review coverage decisions` doc section and JSON records for code review.
- Requires: same-directory temp write, fsync, `os.replace`, and content-hash or mtime CAS.

- [ ] **Step 1: Write failing tests for doc and atomic write behavior**

Create `plugins/superheroes/lib/tests/test_coverage_decisions.py`:

```python
import json
import os
import importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.dirname(HERE)


def load():
    spec = importlib.util.spec_from_file_location("coverage_decisions", os.path.join(LIB, "coverage_decisions.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


CD = load()


def test_doc_decision_appends_bounded_section_atomically(tmp_path):
    doc = tmp_path / "plan.md"
    doc.write_text("# Plan\n\nBody\n", encoding="utf-8")
    before = CD.content_hash(doc.read_text(encoding="utf-8"))
    decision = {"id": "RCD-1-test", "kind": "principle", "classKey": "Test::coverage::missing", "text": "Acceptance tests cover every FR.", "sourceRound": 2}
    result = CD.record_doc_decision(str(doc), decision, expected_hash=before, run_id="run-1")
    assert result["ok"] is True
    text = doc.read_text(encoding="utf-8")
    assert "## Review coverage decisions" in text
    assert "RCD-1-test" in text
    assert "Acceptance tests cover every FR." in text


def test_stale_doc_hash_refuses_write(tmp_path):
    doc = tmp_path / "tasks.md"
    doc.write_text("# Tasks\n", encoding="utf-8")
    result = CD.record_doc_decision(str(doc), {"id": "RCD-1", "text": "x"}, expected_hash="wrong", run_id="run-1")
    assert result == {"ok": False, "reason": "stale"}
    assert doc.read_text(encoding="utf-8") == "# Tasks\n"


def test_failed_replace_leaves_old_doc_readable(tmp_path, monkeypatch):
    doc = tmp_path / "spec.md"
    doc.write_text("# Spec\n", encoding="utf-8")
    before = CD.content_hash(doc.read_text(encoding="utf-8"))
    monkeypatch.setattr(CD.os, "replace", lambda _src, _dst: (_ for _ in ()).throw(OSError("disk full")))
    result = CD.record_doc_decision(str(doc), {"id": "RCD-1", "text": "x"}, expected_hash=before, run_id="run-1")
    assert result["ok"] is False
    assert result["reason"] == "replace-failed"
    assert doc.read_text(encoding="utf-8") == "# Spec\n"


def test_code_decision_record_is_json_array(tmp_path):
    path = tmp_path / "review-coverage-decisions.json"
    result = CD.record_code_decision(str(path), {"id": "RCD-code", "text": "x"}, expected_hash=CD.content_hash(""), run_id="run-1")
    assert result["ok"] is True
    assert json.loads(path.read_text(encoding="utf-8"))[0]["id"] == "RCD-code"


def test_stale_code_decision_hash_refuses_write(tmp_path):
    path = tmp_path / "review-coverage-decisions.json"
    path.write_text("[]\n", encoding="utf-8")
    result = CD.record_code_decision(str(path), {"id": "RCD-stale", "text": "x"}, expected_hash="wrong", run_id="run-2")
    assert result == {"ok": False, "reason": "stale"}
    assert json.loads(path.read_text(encoding="utf-8")) == []


def test_missing_run_id_refuses_write(tmp_path):
    path = tmp_path / "review-coverage-decisions.json"
    result = CD.record_code_decision(str(path), {"id": "RCD-missing", "text": "x"}, expected_hash=CD.content_hash(""))
    assert result == {"ok": False, "reason": "missing-run-id"}
```

- [ ] **Step 2: Run the failing tests**

Run: `python3 -m pytest plugins/superheroes/lib/tests/test_coverage_decisions.py -q`

Expected: FAIL because `coverage_decisions.py` does not exist.

- [ ] **Step 3: Add the coverage decision helper**

Create `plugins/superheroes/lib/coverage_decisions.py`:

```python
#!/usr/bin/env python3
"""Record visible, challengeable review coverage decisions."""
import argparse
import hashlib
import json
import os
import tempfile

SECTION = "## Review coverage decisions"


def content_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _atomic_write(path, text):
    directory = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp = tempfile.mkstemp(prefix=".coverage-decisions-", dir=directory, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
        return {"ok": True}
    except OSError as exc:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        return {"ok": False, "reason": "replace-failed", "detail": str(exc)}


def _entry(decision):
    did = decision.get("id") or "RCD-unknown"
    kind = decision.get("kind") or "coverage"
    key = decision.get("classKey") or ""
    text = decision.get("text") or ""
    source = decision.get("sourceRound")
    payload = json.dumps(decision, sort_keys=True)
    return f"- **{did}** ({kind}; round {source}; class `{key}`): {text}\n  `review-coverage-decision-json:{payload}`\n"


def _with_fence(decision, run_id, lease=None):
    if not run_id:
        return None
    out = dict(decision)
    out["runId"] = run_id
    if lease:
        out["lease"] = lease
    return out


def record_doc_decision(path, decision, expected_hash=None, run_id=None, lease=None):
    decision = _with_fence(decision, run_id, lease)
    if decision is None:
        return {"ok": False, "reason": "missing-run-id"}
    with open(path, encoding="utf-8") as fh:
        original = fh.read()
    if expected_hash and content_hash(original) != expected_hash:
        return {"ok": False, "reason": "stale"}
    entry = _entry(decision)
    if SECTION in original:
        updated = original.rstrip() + "\n" if entry in original else original.rstrip() + "\n" + entry
    else:
        updated = original.rstrip() + "\n\n" + SECTION + "\n\n" + entry
    result = _atomic_write(path, updated)
    if not result["ok"]:
        return result
    return {"ok": True, "id": decision.get("id")}


def record_code_decision(path, decision, expected_hash=None, run_id=None, lease=None):
    decision = _with_fence(decision, run_id, lease)
    if decision is None:
        return {"ok": False, "reason": "missing-run-id"}
    try:
        with open(path, encoding="utf-8") as fh:
            original = fh.read()
        if expected_hash and content_hash(original) != expected_hash:
            return {"ok": False, "reason": "stale"}
        existing = json.loads(original)
        if not isinstance(existing, list):
            existing = []
    except FileNotFoundError:
        original = ""
        if expected_hash and content_hash(original) != expected_hash:
            return {"ok": False, "reason": "stale"}
        existing = []
    except (OSError, ValueError):
        if expected_hash:
            return {"ok": False, "reason": "stale"}
        existing = []
    existing.append(decision)
    result = _atomic_write(path, json.dumps(existing, indent=2) + "\n")
    if not result["ok"]:
        return result
    return {"ok": True, "id": decision.get("id")}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("cmd", choices=["record-doc", "record-code"])
    parser.add_argument("--path", required=True)
    parser.add_argument("--decision-json", required=True)
    parser.add_argument("--expected-hash")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--lease")
    args = parser.parse_args(argv)
    decision = json.loads(args.decision_json)
    if args.cmd == "record-doc":
        result = record_doc_decision(args.path, decision, expected_hash=args.expected_hash, run_id=args.run_id, lease=args.lease)
    else:
        result = record_code_decision(args.path, decision, expected_hash=args.expected_hash, run_id=args.run_id, lease=args.lease)
    print(json.dumps(result))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests and commit**

Run: `python3 -m pytest plugins/superheroes/lib/tests/test_coverage_decisions.py -q`

Expected: PASS.

Commit:

```bash
git add plugins/superheroes/lib/coverage_decisions.py plugins/superheroes/lib/tests/test_coverage_decisions.py
git commit -m "feat(superheroes): record atomic coverage decisions"
```

### Task 4: Add Telemetry Completeness

**Files:**
- Create: `plugins/superheroes/lib/review_telemetry.py`
- Create: `plugins/superheroes/lib/tests/test_review_telemetry.py`
- Modify: `plugins/superheroes/lib/loop_readout.py`
- Modify: `plugins/superheroes/lib/tests/test_loop_readout.py`

**Interfaces:**
- Produces: `review-telemetry.json` with per-leaf usage completeness and benchmark-validity state.

- [ ] **Step 1: Write failing telemetry tests**

Create `plugins/superheroes/lib/tests/test_review_telemetry.py`:

```python
import importlib.util
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.dirname(HERE)


def load():
    spec = importlib.util.spec_from_file_location("review_telemetry", os.path.join(LIB, "review_telemetry.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


RT = load()


def test_complete_usage_is_benchmark_valid(tmp_path):
    record = RT.build_record(
        rounds=[{"round": 1, "dimensions": {"code-reviewer": {"status": "run", "tier": "reviewer-deep"}}}],
        expected_leaves=["code-reviewer:r1", "synthesis:r1"],
        usage={"code-reviewer:r1": {"input": 3, "output": 4, "total": 7}, "synthesis:r1": {"input": 1, "output": 2, "total": 3}},
        benchmark=True,
    )
    assert record["tokenUsage"]["complete"] is True
    assert record["benchmarkValid"] is True
    assert record["tokenUsage"]["total"] == 10


def test_partial_usage_is_not_benchmark_valid(tmp_path):
    record = RT.build_record(
        rounds=[{"round": 1, "dimensions": {}}],
        expected_leaves=["code-reviewer:r1", "synthesis:r1"],
        usage={"code-reviewer:r1": {"total": 7}},
        benchmark=True,
    )
    assert record["tokenUsage"]["complete"] is False
    assert record["benchmarkValid"] is False
    assert record["tokenUsage"]["missing"] == ["synthesis:r1"]


def test_dimension_counts_record_run_skip_and_tiers():
    record = RT.build_record(
        rounds=[{"round": 1, "dimensions": {"test-reviewer": {"status": "run", "tier": "reviewer-deep"}, "security-reviewer": {"status": "skipped", "tier": "reviewer-deep", "escalated": True}}}],
        expected_leaves=["test-reviewer:r1"],
        usage={"test-reviewer:r1": {"total": 7}},
        benchmark=False,
    )
    assert record["dimensionCounts"]["test-reviewer"]["run"] == 1
    assert record["dimensionCounts"]["security-reviewer"]["skipped"] == 1
    assert record["dimensionCounts"]["test-reviewer"]["deep"] == 1
    assert record["dimensionCounts"]["security-reviewer"]["escalated"] == 1


def test_write_failure_does_not_change_terminal(tmp_path, monkeypatch):
    path = tmp_path / "review-telemetry.json"
    record = RT.build_record(rounds=[], expected_leaves=[], usage={}, benchmark=False, terminal="clean")
    monkeypatch.setattr(RT, "_atomic_write", lambda _path, _text: {"ok": False, "reason": "write-failed"})
    result = RT.write_record(str(path), record, expected_hash=RT.content_hash(""), run_id="run-1")
    assert result["ok"] is False
    assert record["terminal"] == "clean"


def test_stale_telemetry_write_refuses_to_overwrite(tmp_path):
    path = tmp_path / "review-telemetry.json"
    path.write_text('{"schemaVersion":1}\n', encoding="utf-8")
    record = RT.build_record(rounds=[], expected_leaves=[], usage={}, benchmark=False, terminal="clean")
    result = RT.write_record(str(path), record, expected_hash="wrong", run_id="run-2")
    assert result == {"ok": False, "reason": "stale"}
    assert path.read_text(encoding="utf-8") == '{"schemaVersion":1}\n'
```

Add to `plugins/superheroes/lib/tests/test_loop_readout.py`:

```python
def test_partial_telemetry_named_not_benchmark_valid():
    out = LR.render(_record(telemetry={"benchmarkValid": False, "tokenUsage": {"complete": False, "missing": ["synthesis:r1"]}}))
    assert "not benchmark-valid" in out
    assert "synthesis:r1" in out


def test_complete_telemetry_renders_counts_and_tokens():
    out = LR.render(_record(telemetry={"roundCount": 2, "benchmarkValid": True, "tokenUsage": {"complete": True, "total": 42}, "dimensionCounts": {"test-reviewer": {"run": 2, "skipped": 0, "cheap": 1, "deep": 1, "escalated": 1}}}))
    assert "Telemetry: 2 rounds" in out
    assert "test-reviewer: run 2" in out
    assert "tokens 42" in out


def test_readout_renders_coverage_decisions_and_challenges():
    out = LR.render(_record(coverageDecisions=[
        {"id": "RCD-1", "classKey": "Test::coverage::missing acceptance test", "text": "Acceptance fixtures cover repeated missing-test findings.", "sourceRound": 2},
        {"id": "RCD-bad", "classKey": "Security::leak", "text": "Security-only changes never affect readouts.", "challengedBy": "security-reviewer"},
    ]))
    assert "Coverage decisions:" in out
    assert "RCD-1" in out
    assert "Test::coverage::missing acceptance test" in out
    assert "challenged by security-reviewer" in out
```

- [ ] **Step 2: Run failing tests**

Run: `python3 -m pytest plugins/superheroes/lib/tests/test_review_telemetry.py plugins/superheroes/lib/tests/test_loop_readout.py -q`

Expected: FAIL because `review_telemetry.py` and readout telemetry rendering are missing.

- [ ] **Step 3: Add telemetry helper**

Create `plugins/superheroes/lib/review_telemetry.py`:

```python
#!/usr/bin/env python3
"""Local telemetry record for the shared review loop."""
import argparse
import hashlib
import json
import os
import tempfile


def content_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _atomic_write(path, text):
    directory = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp = tempfile.mkstemp(prefix=".review-telemetry-", dir=directory, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
        return {"ok": True}
    except OSError as exc:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        return {"ok": False, "reason": "write-failed", "detail": str(exc)}


def build_record(rounds, expected_leaves, usage, benchmark=False, terminal=None):
    expected = list(expected_leaves or [])
    usage = usage or {}
    missing = [leaf for leaf in expected if leaf not in usage]
    total = sum(int((usage.get(leaf) or {}).get("total") or 0) for leaf in expected if leaf in usage)
    complete = len(missing) == 0
    dimension_counts = {}
    for rec in rounds or []:
        for name, dim in (rec.get("dimensions") or {}).items():
            counts = dimension_counts.setdefault(name, {"run": 0, "skipped": 0, "cheap": 0, "deep": 0, "escalated": 0})
            status = dim.get("status")
            if status == "skipped":
                counts["skipped"] += 1
            elif status == "run":
                counts["run"] += 1
            tier = dim.get("tier")
            if tier == "reviewer":
                counts["cheap"] += 1
            elif tier == "reviewer-deep":
                counts["deep"] += 1
            if dim.get("escalated"):
                counts["escalated"] += 1
    return {
        "schemaVersion": 1,
        "terminal": terminal,
        "roundCount": len(rounds or []),
        "rounds": rounds or [],
        "tokenUsage": {
            "complete": complete,
            "expectedLeaves": expected,
            "present": sorted([leaf for leaf in expected if leaf in usage]),
            "missing": missing,
            "total": total,
        },
        "dimensionCounts": dimension_counts,
        "benchmarkValid": bool(complete or not benchmark),
    }


def _current_hash(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return content_hash(fh.read())
    except FileNotFoundError:
        return content_hash("")


def write_record(path, record, expected_hash=None, run_id=None, lease=None):
    if not run_id:
        return {"ok": False, "reason": "missing-run-id"}
    if expected_hash and _current_hash(path) != expected_hash:
        return {"ok": False, "reason": "stale"}
    record = dict(record)
    record["runId"] = run_id
    if lease:
        record["lease"] = lease
    return _atomic_write(path, json.dumps(record, indent=2) + "\n")


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("cmd", choices=["write"])
    parser.add_argument("--path", required=True)
    parser.add_argument("--payload-json", required=True)
    parser.add_argument("--expected-hash")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--lease")
    args = parser.parse_args(argv)
    record = json.loads(args.payload_json)
    result = write_record(args.path, record, expected_hash=args.expected_hash, run_id=args.run_id, lease=args.lease)
    print(json.dumps(result))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Extend readout renderer**

In `plugins/superheroes/lib/loop_readout.py`, add this rendering block inside `render(record)` after terminal/reason lines and before fixes/drops:

```python
    decisions = record.get("coverageDecisions") if isinstance(record, dict) else None
    if isinstance(decisions, list) and decisions:
        lines.append("")
        lines.append("Coverage decisions:")
        for decision in decisions:
            if not isinstance(decision, dict):
                continue
            text = f"- {decision.get('id', 'unknown')} ({decision.get('classKey', 'unknown')}): {decision.get('text', '')}"
            if decision.get("challengedBy"):
                text += f" [challenged by {decision.get('challengedBy')}]"
            lines.append(text)

    telemetry = record.get("telemetry") if isinstance(record, dict) else None
    if isinstance(telemetry, dict):
        usage = telemetry.get("tokenUsage") or {}
        if usage.get("complete") is True:
            lines.append("")
            lines.append(f"Telemetry: {telemetry.get('roundCount', 0)} rounds, tokens {usage.get('total', 0)}")
            for name, counts in sorted((telemetry.get("dimensionCounts") or {}).items()):
                lines.append(f"{name}: run {counts.get('run', 0)}, skipped {counts.get('skipped', 0)}, cheap {counts.get('cheap', 0)}, deep {counts.get('deep', 0)}, escalated {counts.get('escalated', 0)}")
        if telemetry.get("benchmarkValid") is False:
            lines.append("")
            lines.append("Telemetry: partial / not benchmark-valid")
            missing = usage.get("missing") or []
            if missing:
                lines.append("Missing token usage: " + ", ".join(str(x) for x in missing))
```

Keep the existing unknown-schema and non-dict behavior unchanged.

- [ ] **Step 5: Run tests and commit**

Run: `python3 -m pytest plugins/superheroes/lib/tests/test_review_telemetry.py plugins/superheroes/lib/tests/test_loop_readout.py -q`

Expected: PASS.

Commit:

```bash
git add plugins/superheroes/lib/review_telemetry.py plugins/superheroes/lib/tests/test_review_telemetry.py plugins/superheroes/lib/loop_readout.py plugins/superheroes/lib/tests/test_loop_readout.py
git commit -m "feat(superheroes): record review telemetry completeness"
```

### Task 5: Tighten Terminal Gates and Code-Review Advancement

**Files:**
- Modify: `plugins/superheroes/lib/front_half.py`
- Modify: `plugins/superheroes/lib/front_half.js`
- Modify: `plugins/superheroes/lib/tests/parity/front_half/gateForTerminal/02_clean_with_skips.json`
- Modify: `plugins/superheroes/lib/showrunner.js`
- Modify: `plugins/superheroes/lib/tests/showrunner_reviewcode_loop_smoke.js`

**Interfaces:**
- Produces: blocking `clean-with-skips` maps to `changes-requested`; only true `clean` advances.

- [ ] **Step 1: Update the failing expectations**

Change `plugins/superheroes/lib/tests/parity/front_half/gateForTerminal/02_clean_with_skips.json` to:

```json
{
  "input": ["clean-with-skips"],
  "expected": "changes-requested"
}
```

In `plugins/superheroes/lib/tests/showrunner_reviewcode_loop_smoke.js`, change the clean-with-skips scenario assertions to:

```js
  assert.strictEqual(r.gate, 'changes-requested', 'clean-with-skips parks while a blocking tail exists')
  assert.strictEqual(calls.prov, 0, 'clean-with-skips records NO covers stamp')
```

- [ ] **Step 2: Run failing tests**

Run: `python3 -m pytest plugins/superheroes/lib/tests/test_parity.py -q`

Expected: FAIL because `front_half` still maps `clean-with-skips` to passed.

Run: `node plugins/superheroes/lib/tests/showrunner_reviewcode_loop_smoke.js`

Expected: FAIL because `reviewCodePhase` still advances `clean-with-skips`.

- [ ] **Step 3: Update front-half gate mapping**

Change `plugins/superheroes/lib/front_half.py`:

```python
def gate_for_terminal(terminal):
    """Map a review terminal onto a definition-doc review gate value.

    Only a true clean terminal can pass. A blocking clean-with-skips result is
    visible but does not advance.
    """
    return "passed" if terminal == "clean" else "changes-requested"
```

Change `plugins/superheroes/lib/front_half.js`:

```js
function gateForTerminal(terminal) {
  return terminal === 'clean' ? 'passed' : 'changes-requested'
}
```

- [ ] **Step 4: Update code-review advancement**

Change `plugins/superheroes/lib/showrunner.js`:

```js
const ADVANCE_TERMINALS = new Set(['clean'])
```

Leave the existing `terminal === 'clean'` covers-stamp guard in place.

- [ ] **Step 5: Run tests and commit**

Run: `python3 -m pytest plugins/superheroes/lib/tests/test_parity.py plugins/superheroes/lib/tests/test_front_half.py -q`

Expected: PASS.

Run: `node plugins/superheroes/lib/tests/showrunner_reviewcode_loop_smoke.js`

Expected: PASS and output includes `ok: reviewCodePhase`.

Commit:

```bash
git add plugins/superheroes/lib/front_half.py plugins/superheroes/lib/front_half.js plugins/superheroes/lib/tests/parity/front_half/gateForTerminal/02_clean_with_skips.json plugins/superheroes/lib/showrunner.js plugins/superheroes/lib/tests/showrunner_reviewcode_loop_smoke.js
git commit -m "fix(superheroes): stop advancing skipped blocking reviews"
```

### Task 6: Extend Panel Tally for Result Confidence and Carried Dimensions

**Files:**
- Modify: `plugins/superheroes/lib/panel_tally.py`
- Modify: `plugins/superheroes/lib/panel_tally.js`
- Modify: `plugins/superheroes/lib/tests/test_panel_tally.py`
- Add parity fixtures under `plugins/superheroes/lib/tests/parity/panel_tally/roundGate/`

**Interfaces:**
- Consumes: dimension result objects with `status`, `findings`, `confidence`, `verificationReceipt`, `carried`.
- Produces: fail-closed low confidence for missing final receipts and carried findings that do not count as new recurrence.

- [ ] **Step 1: Add failing tests**

Append to `plugins/superheroes/lib/tests/test_panel_tally.py`:

```python
def test_round_gate_low_when_final_clean_lacks_receipt():
    result = {"status": "run", "findings": [], "confidence": "high"}
    gate, conf, missing = PT.round_gate_from_dimension_results({"code": result}, ["code"], final_confirmation=True)
    assert gate == "cannot-certify"
    assert conf == "low"


def test_round_gate_low_when_baseline_clean_is_low_confidence():
    result = {"status": "run", "findings": [], "confidence": "low"}
    gate, conf, missing = PT.round_gate_from_dimension_results({"code": result}, ["code"], final_confirmation=False)
    assert gate == "cannot-certify"
    assert conf == "low"


def test_round_gate_low_when_confidence_missing():
    result = {"status": "run", "findings": []}
    gate, conf, missing = PT.round_gate_from_dimension_results({"code": result}, ["code"], final_confirmation=False)
    assert gate == "cannot-certify"
    assert conf == "low"


def test_round_gate_high_when_final_clean_has_receipt():
    result = {"status": "run", "findings": [], "confidence": "high", "verificationReceipt": {"artifact": "run-1:round-3", "chain": [{"step": "citation", "evidence": "reviewed source citations"}, {"step": "reachability", "evidence": "validated changed call path"}, {"step": "missing-check", "evidence": "searched for uncovered FRs"}, {"step": "tooling", "evidence": "pytest smoke passed"}], "coverageDecisionIds": ["RCD-1"]}}
    gate, conf, missing = PT.round_gate_from_dimension_results({"code": result}, ["code"], final_confirmation=True, receipt_context={"artifact": "run-1:round-3", "coverageDecisionIds": ["RCD-1"]})
    assert gate == "clean"
    assert conf == "high"


def test_round_gate_low_when_receipt_has_labels_without_evidence():
    result = {"status": "run", "findings": [], "confidence": "high", "verificationReceipt": {"chain": ["citation", "reachability", "missing-check", "tooling"]}}
    gate, conf, missing = PT.round_gate_from_dimension_results({"code": result}, ["code"], final_confirmation=True)
    assert gate == "cannot-certify"
    assert conf == "low"


def test_round_gate_low_when_receipt_artifact_is_stale():
    result = {"status": "run", "findings": [], "confidence": "high", "verificationReceipt": {"artifact": "old-run", "chain": [{"step": "citation", "evidence": "x"}, {"step": "reachability", "evidence": "x"}, {"step": "missing-check", "evidence": "x"}, {"step": "tooling", "evidence": "x"}], "coverageDecisionIds": ["RCD-1"]}}
    gate, conf, missing = PT.round_gate_from_dimension_results({"code": result}, ["code"], final_confirmation=True, receipt_context={"artifact": "run-1:round-3", "coverageDecisionIds": ["RCD-1"]})
    assert gate == "cannot-certify"
    assert conf == "low"


def test_round_gate_low_when_receipt_omits_current_decision():
    result = {"status": "run", "findings": [], "confidence": "high", "verificationReceipt": {"artifact": "run-1:round-3", "chain": [{"step": "citation", "evidence": "x"}, {"step": "reachability", "evidence": "x"}, {"step": "missing-check", "evidence": "x"}, {"step": "tooling", "evidence": "x"}], "coverageDecisionIds": []}}
    gate, conf, missing = PT.round_gate_from_dimension_results({"code": result}, ["code"], final_confirmation=True, receipt_context={"artifact": "run-1:round-3", "coverageDecisionIds": ["RCD-1"]})
    assert gate == "cannot-certify"
    assert conf == "low"


def test_carried_blocker_counts_but_is_marked_carried():
    carried = {"status": "skipped", "carriedFromRound": 1, "findings": [{"file": "a.py", "line": 1, "title": "bug", "severity": "Important"}]}
    compiled = PT.compile_dimension_results({"code": carried})
    assert compiled[0]["carried"] is True
    assert compiled[0]["sourceRound"] == 1
```

- [ ] **Step 2: Run failing test**

Run: `python3 -m pytest plugins/superheroes/lib/tests/test_panel_tally.py -q`

Expected: FAIL because `round_gate_from_dimension_results` and `compile_dimension_results` do not exist.

- [ ] **Step 3: Add Python functions**

Add to `plugins/superheroes/lib/panel_tally.py`:

```python
def compile_dimension_results(results):
    findings = []
    for name, result in (results or {}).items():
        for f in result.get("findings") or []:
            item = dict(f)
            item.setdefault("dimension", result.get("dimension") or name)
            if result.get("status") == "skipped":
                item["carried"] = True
                item["sourceRound"] = result.get("carriedFromRound")
            findings.append(item)
    return compile_findings(findings)


def _valid_final_receipt(result, receipt_context=None):
    receipt = result.get("verificationReceipt")
    chain = receipt.get("chain") if isinstance(receipt, dict) else None
    required = {"citation", "reachability", "missing-check", "tooling"}
    if not isinstance(receipt, dict) or not receipt.get("artifact"):
        return False
    if not isinstance(receipt.get("coverageDecisionIds"), list):
        return False
    ctx = receipt_context or {}
    if ctx.get("artifact") and receipt.get("artifact") != ctx.get("artifact"):
        return False
    needed_ids = set(ctx.get("coverageDecisionIds") or [])
    if needed_ids and not needed_ids.issubset(set(receipt.get("coverageDecisionIds") or [])):
        return False
    seen = set()
    for step in chain or []:
        if not isinstance(step, dict):
            return False
        if not step.get("evidence"):
            return False
        seen.add(step.get("step"))
    return required.issubset(seen)


def round_gate_from_dimension_results(results, expected_roster, final_confirmation=False, receipt_context=None):
    completed = [name for name, result in (results or {}).items() if result.get("status") in ("run", "skipped")]
    compiled = compile_dimension_results(results)
    gate, confidence, missing = round_gate(compiled, expected_roster, completed)
    for name in expected_roster:
        result = (results or {}).get(name) or {}
        if result.get("confidence") != "high":
            return "cannot-certify", "low", missing
    if final_confirmation:
        for name in expected_roster:
            result = (results or {}).get(name) or {}
            if not _valid_final_receipt(result, receipt_context):
                return "cannot-certify", "low", missing
    return gate, confidence, missing
```

Add these functions to `plugins/superheroes/lib/panel_tally.js` and export them:

```js
function compileDimensionResults(results) {
  const findings = []
  for (const [name, result] of Object.entries(results || {})) {
    for (const f of result.findings || []) {
      const item = Object.assign({}, f)
      if (!item.dimension) item.dimension = result.dimension || name
      if (result.status === 'skipped') {
        item.carried = true
        item.sourceRound = result.carriedFromRound
      }
      findings.push(item)
    }
  }
  return compileFindings(findings)
}

function _validFinalReceipt(result, receiptContext) {
  const receipt = result && result.verificationReceipt
  if (!receipt || !receipt.artifact || !Array.isArray(receipt.coverageDecisionIds)) return false
  receiptContext = receiptContext || {}
  if (receiptContext.artifact && receipt.artifact !== receiptContext.artifact) return false
  const needed = new Set(receiptContext.coverageDecisionIds || [])
  const gotIds = new Set(receipt.coverageDecisionIds || [])
  for (const id of needed) if (!gotIds.has(id)) return false
  const chain = Array.isArray(receipt.chain) ? receipt.chain : []
  const got = new Set()
  for (const step of chain) {
    if (!step || typeof step !== 'object' || !step.evidence) return false
    got.add(step.step)
  }
  return ['citation', 'reachability', 'missing-check', 'tooling'].every((x) => got.has(x))
}

function roundGateFromDimensionResults(results, expectedRoster, finalConfirmation, receiptContext) {
  const completed = Object.entries(results || {})
    .filter(([, result]) => result.status === 'run' || result.status === 'skipped')
    .map(([name]) => name)
  const compiled = compileDimensionResults(results)
  const base = roundGate(compiled, expectedRoster, completed)
  for (const name of expectedRoster) {
    const result = (results || {})[name] || {}
    if (result.confidence !== 'high') return { gate: 'cannot-certify', confidence: 'low', incomplete: base.incomplete }
  }
  if (finalConfirmation) {
    for (const name of expectedRoster) {
      const result = (results || {})[name] || {}
      if (!_validFinalReceipt(result, receiptContext)) {
        return { gate: 'cannot-certify', confidence: 'low', incomplete: base.incomplete }
      }
    }
  }
  return base
}
```

- [ ] **Step 4: Add parity fixtures for the new functions**

Create `plugins/superheroes/lib/tests/parity/panel_tally/compileDimensionResults/01_carried_blocker.json`:

```json
{
  "input": [{
    "code": {
      "status": "skipped",
      "carriedFromRound": 1,
      "findings": [{"file": "a.py", "line": 1, "title": "bug", "severity": "Important"}]
    }
  }],
  "expected": [{"file": "a.py", "line": 1, "title": "bug", "severity": "Important", "dimension": "code", "carried": true, "sourceRound": 1, "classification": "mechanical"}]
}
```

Create `plugins/superheroes/lib/tests/parity/panel_tally/roundGateFromDimensionResults/01_final_missing_receipt_low.json`:

```json
{
  "input": [{"code": {"status": "run", "findings": [], "confidence": "high"}}, ["code"], true],
  "expected": {"gate": "cannot-certify", "confidence": "low", "incomplete": []}
}
```

Create `plugins/superheroes/lib/tests/parity/panel_tally/roundGateFromDimensionResults/02_final_receipt_clean.json`:

```json
{
  "input": [{"code": {"status": "run", "findings": [], "confidence": "high", "verificationReceipt": {"artifact": "run-1:round-3", "chain": [{"step": "citation", "evidence": "reviewed citations"}, {"step": "reachability", "evidence": "validated call path"}, {"step": "missing-check", "evidence": "checked missing FRs"}, {"step": "tooling", "evidence": "pytest smoke passed"}], "coverageDecisionIds": ["RCD-1"]}}}, ["code"], true],
  "expected": {"gate": "clean", "confidence": "high", "incomplete": []}
}
```

Create `plugins/superheroes/lib/tests/parity/panel_tally/roundGateFromDimensionResults/03_baseline_low_confidence_cannot_certify.json`:

```json
{
  "input": [{"code": {"status": "run", "findings": [], "confidence": "low"}}, ["code"], false],
  "expected": {"gate": "cannot-certify", "confidence": "low", "incomplete": []}
}
```

Register both functions in `plugins/superheroes/lib/tests/test_parity.py`:

```python
("panel_tally", "compileDimensionResults", "panel_tally", "compile_dimension_results"),
("panel_tally", "roundGateFromDimensionResults", "panel_tally", "round_gate_from_dimension_results"),
```

Add the tuple normalization for the new Python helper:

```python
("panel_tally", "round_gate_from_dimension_results"): ["gate", "confidence", "incomplete"],
```

- [ ] **Step 5: Run tests and commit**

Run: `python3 -m pytest plugins/superheroes/lib/tests/test_panel_tally.py plugins/superheroes/lib/tests/test_parity.py -q`

Expected: PASS.

Commit:

```bash
git add plugins/superheroes/lib/panel_tally.py plugins/superheroes/lib/panel_tally.js plugins/superheroes/lib/tests/test_panel_tally.py plugins/superheroes/lib/tests/parity/panel_tally plugins/superheroes/lib/tests/test_parity.py
git commit -m "feat(superheroes): tally confident carried dimension results"
```

### Task 7: Wire the Shared Shell to Policy, Memory, Coverage, and Telemetry

**Files:**
- Modify: `plugins/superheroes/lib/review_panel_shell.js`
- Modify: `plugins/superheroes/lib/showrunner.js`
- Modify: `plugins/superheroes/lib/io_seam.js`
- Modify: `plugins/superheroes/lib/bundle_showrunner.js`
- Modify: `plugins/superheroes/lib/tests/showrunner_panel_shell_smoke.js`
- Modify: `plugins/superheroes/lib/tests/showrunner_reviewcode_loop_smoke.js`

**Interfaces:**
- Consumes: `review_round_policy`, `review_memory`, `coverage_decisions`, `review_telemetry`, extended reviewer result shape.

- [ ] **Step 1: Add failing shell smoke cases**

Append to `plugins/superheroes/lib/tests/showrunner_panel_shell_smoke.js`:

```js
  function receipt(runId, round, opts = {}) {
    return { artifact: `${runId}:round-${round}`, chain: [{ step: 'citation', evidence: 'reviewed citations' }, { step: 'reachability', evidence: 'validated call path' }, { step: 'missing-check', evidence: 'checked missing FRs' }, { step: 'tooling', evidence: 'smoke passed' }], coverageDecisionIds: ((opts.coverageDecisions || []).map((d) => d.id).filter(Boolean)) }
  }

  // 8. confirmation after a fix: round 1 blocks, round 2 resolves, round 3 confirms full/deep.
  {
    const dir = freshDir()
    const seen = []
    const fixRounds = []
    let calls = 0
    global.reviewerAgent = async (reviewer, context, rubric, runDir, round, opts) => {
      seen.push({ reviewer, round, tier: opts && opts.tier, kind: opts && opts.roundKind })
      calls += 1
      if (calls === 1) return { findings: BLOCKER, confidence: 'high', verificationReceipt: receipt(runDir, round, opts) }
      return { findings: [], confidence: 'high', verificationReceipt: receipt(runDir, round, opts) }
    }
    v = await reviewPanel({ ...base(dir), reviewerSet: ['test-reviewer', 'security-reviewer'], fixStep: async (_ctx, verdict) => { fixRounds.push(verdict.round); return { fixed: ['bug'], changedSubjects: ['Test'], coverageDecisions: [] } } })
    assert.strictEqual(v.terminal, 'clean')
    const confirmation = seen.filter((x) => x.kind === 'confirmation')
    assert.deepStrictEqual(confirmation.map((x) => x.reviewer).sort(), ['security-reviewer', 'test-reviewer'])
    assert.ok(confirmation.every((x) => x.tier === 'reviewer-deep'))
    const finalRound = Math.max(...confirmation.map((x) => x.round))
    assert.ok(fixRounds.every((r) => r < finalRound))
  }

  // 9a. first-round high-confidence clean still certifies without final-confirmation receipt.
  {
    const dir = freshDir()
    global.reviewerAgent = async () => ({ findings: [], confidence: 'high' })
    v = await reviewPanel({ ...base(dir), reviewerSet: ['code-reviewer'], legKind: { panel: true, code: false } })
    assert.strictEqual(v.terminal, 'clean')
  }

  // 9b. post-fix final confirmation without receipt cannot certify.
  {
    const dir = freshDir()
    let first = true
    global.reviewerAgent = async (reviewer, context, rubric, runDir, round, opts) => {
      if (first) {
        first = false
        return { findings: BLOCKER, confidence: 'high', verificationReceipt: receipt(runDir, round, opts) }
      }
      return { findings: [], confidence: 'high' }
    }
    v = await reviewPanel({ ...base(dir), reviewerSet: ['code-reviewer'], legKind: { panel: true, code: false }, fixStep: async () => ({ changedSubjects: ['Code'], coverageDecisions: [] }) })
    assert.notStrictEqual(v.terminal, 'clean')
  }

  // 9c. stale final-confirmation receipt artifact cannot certify.
  {
    const dir = freshDir()
    let first = true
    global.reviewerAgent = async (reviewer, context, rubric, runDir, round, opts) => {
      if (first) {
        first = false
        return { findings: BLOCKER, confidence: 'high', verificationReceipt: receipt(runDir, round, opts) }
      }
      return { findings: [], confidence: 'high', verificationReceipt: Object.assign(receipt(runDir, round, opts), { artifact: 'old-run:round-9' }) }
    }
    v = await reviewPanel({ ...base(dir), reviewerSet: ['code-reviewer'], legKind: { panel: true, code: false }, fixStep: async () => ({ changedSubjects: ['Code'], coverageDecisions: [] }) })
    assert.notStrictEqual(v.terminal, 'clean')
  }

  // 10. cheap low-confidence results escalate before they can influence a gate.
  {
    const dir = freshDir()
    const seen = []
    let first = true
    global.reviewerAgent = async (reviewer, context, rubric, runDir, round, opts) => {
      seen.push({ reviewer, tier: opts && opts.tier, roundKind: opts && opts.roundKind })
      if (first) {
        first = false
        return { findings: BLOCKER, confidence: 'high', verificationReceipt: receipt(runDir, round, opts), usage: { total: 20 } }
      }
      if (opts && opts.tier === 'reviewer') return { findings: [], confidence: 'low', usage: { total: 1 } }
      return { findings: [], confidence: 'high', verificationReceipt: receipt(runDir, round, opts), usage: { total: 10 } }
    }
    v = await reviewPanel({ ...base(dir), reviewerSet: ['test-reviewer'], legKind: { panel: true, code: false }, fixStep: async () => ({ changedSubjects: ['Test'], coverageDecisions: [] }) })
    assert.ok(seen.some((x) => x.tier === 'reviewer'))
    assert.ok(seen.some((x) => x.tier === 'reviewer-deep'))
    assert.strictEqual(v.terminal, 'clean')
  }

  // 11. coverage decisions are recorded and passed to later reviewer context.
  {
    const dir = freshDir()
    const contexts = []
    const seenCoverageOptions = []
    let roundSeen = 0
    global.reviewerAgent = async (reviewer, context, rubric, runDir, round, opts) => {
      contexts.push(context)
      seenCoverageOptions.push(((opts && opts.coverageDecisions) || []).map((d) => d.id))
      roundSeen = Math.max(roundSeen, round)
      if (round === 1) return { findings: BLOCKER, confidence: 'high', verificationReceipt: receipt(runDir, round, opts) }
      return { findings: [], confidence: 'high', verificationReceipt: receipt(runDir, round, opts) }
    }
    v = await reviewPanel({ ...base(dir), reviewerSet: ['test-reviewer'], fixStep: async () => ({ changedSubjects: ['Test'], coverageDecisions: [{ id: 'RCD-1', classKey: 'Test::coverage::missing', text: 'Covered by integration fixture' }] }) })
    assert.ok(roundSeen >= 2)
    assert.ok(contexts.some((ctx) => JSON.stringify(ctx).includes('RCD-1')))
    assert.ok(seenCoverageOptions.some((ids) => ids.includes('RCD-1')))
    assert.strictEqual(v.terminal, 'clean')
  }

  // 12. corrupt resumed round memory cannot certify even if the next reviewer is clean.
  {
    const dir = freshDir()
    await io().writeFile(io().join(dir, 'round-records.json'), '{corrupt json')
    global.reviewerAgent = async (reviewer, context, rubric, runDir, round, opts) => ({ findings: [], confidence: 'high', verificationReceipt: receipt(runDir, round, opts) })
    v = await reviewPanel({ ...base(dir), reviewerSet: ['test-reviewer'] })
    assert.notStrictEqual(v.terminal, 'clean')
    assert.match(v.reason || '', /round-memory/)
  }

  // 13. resume rebuilds fix context from v2 memory and recorded coverage decisions.
  {
    const dir = freshDir()
    await io().writeFile(io().join(dir, 'round-records.json'), JSON.stringify([{
      schemaVersion: 2,
      round: 1,
      kind: 'baseline',
      dimensions: { 'test-reviewer': { status: 'run', confidence: 'high', findings: BLOCKER, hasFindings: true, subjects: ['Test'] } },
      findings: BLOCKER,
      changedSubjects: ['Test'],
      coverageDecisions: [{ id: 'RCD-resume', classKey: 'Test::coverage::missing' }],
    }]))
    await io().writeFile(io().join(dir, 'review-coverage-decisions.json'), JSON.stringify([{ id: 'RCD-resume', classKey: 'Test::coverage::missing' }]))
    let captured = null
    global.reviewerAgent = async (reviewer, context, rubric, runDir, round, opts) => ({ findings: BLOCKER, confidence: 'high', verificationReceipt: receipt(runDir, round, opts) })
    v = await reviewPanel({ ...base(dir), reviewerSet: ['test-reviewer'], fixStep: async (ctx) => { captured = ctx; return { changedSubjects: ['Test'], coverageDecisions: [] } } })
    assert.ok(captured.priorFindings.length > 0)
    assert.ok(captured.classKeys.some((k) => k.includes('Test::coverage')))
    assert.ok(captured.changedSubjects.includes('Test'))
    assert.ok(captured.coverageDecisions.some((d) => d.id === 'RCD-resume'))
  }

  // 13b. resume after a successful fix enters full confirmation from durable memory.
  {
    const dir = freshDir()
    await io().writeFile(io().join(dir, 'round-records.json'), JSON.stringify([{
      schemaVersion: 2,
      round: 1,
      kind: 'baseline',
      dimensions: { 'test-reviewer': { status: 'run', confidence: 'high', findings: BLOCKER, hasFindings: true, subjects: ['Test'] } },
      findings: BLOCKER,
      changedSubjects: ['Test'],
      coverageDecisions: [],
      confirmationPending: true,
    }]))
    const seen = []
    global.reviewerAgent = async (reviewer, context, rubric, runDir, round, opts) => {
      seen.push({ reviewer, round, tier: opts && opts.tier, roundKind: opts && opts.roundKind })
      return { findings: [], confidence: 'high', verificationReceipt: receipt(runDir, round, opts), usage: { total: 1 } }
    }
    v = await reviewPanel({ ...base(dir), reviewerSet: ['test-reviewer', 'security-reviewer'] })
    assert.strictEqual(v.terminal, 'clean')
    assert.deepStrictEqual(seen.map((x) => x.reviewer).sort(), ['security-reviewer', 'test-reviewer'])
    assert.ok(seen.every((x) => x.roundKind === 'confirmation' && x.tier === 'reviewer-deep'))
  }

  // 13c. post-fix confirmation marker write failure fails closed.
  {
    const dir = freshDir()
    const oldIo = global.io
    const baseIo = io()
    let persists = 0
    global.io = Object.assign({}, baseIo, { runHelper: async (cmd, args) => {
      if (String((args || [])[0]).includes('review_memory.py') && (args || []).includes('persist')) {
        persists += 1
        if (persists === 2) return { ok: false, stdout: '{"ok":false,"reason":"forced-post-fix"}' }
      }
      return baseIo.runHelper(cmd, args)
    } })
    global.reviewerAgent = async (reviewer, context, rubric, runDir, round, opts) => {
      if (round === 1) return { findings: BLOCKER, confidence: 'high', verificationReceipt: receipt(runDir, round, opts), usage: { total: 1 } }
      return { findings: [], confidence: 'high', verificationReceipt: receipt(runDir, round, opts), usage: { total: 1 } }
    }
    v = await reviewPanel({ ...base(dir), reviewerSet: ['test-reviewer'], fixStep: async () => ({ changedSubjects: ['Test'], coverageDecisions: [] }) })
    global.io = oldIo
    assert.notStrictEqual(v.terminal, 'clean')
    assert.ok(persists >= 2)
  }

  // 13d. resume cannot certify from a post-fix marker whose coverage decision is not visible.
  {
    const dir = freshDir()
    await io().writeFile(io().join(dir, 'round-records.json'), JSON.stringify([{
      schemaVersion: 2,
      round: 1,
      kind: 'baseline',
      dimensions: { 'test-reviewer': { status: 'run', confidence: 'high', findings: BLOCKER, hasFindings: true, subjects: ['Test'] } },
      findings: BLOCKER,
      changedSubjects: ['Test'],
      coverageDecisions: [{ id: 'RCD-lost', classKey: 'Test::coverage::missing' }],
      confirmationPending: true,
    }]))
    await io().writeFile(io().join(dir, 'review-coverage-decisions.json'), '[]')
    global.reviewerAgent = async (reviewer, context, rubric, runDir, round, opts) => ({ findings: [], confidence: 'high', verificationReceipt: receipt(runDir, round, opts), usage: { total: 1 } })
    v = await reviewPanel({ ...base(dir), reviewerSet: ['test-reviewer'] })
    assert.notStrictEqual(v.terminal, 'clean')
    assert.match(v.reason || '', /coverage-decision/)
  }

  // 14. malformed coverage-decision JSON fails closed.
  {
    const dir = freshDir()
    await io().writeFile(io().join(dir, 'review-coverage-decisions.json'), '{bad json')
    global.reviewerAgent = async (reviewer, context, rubric, runDir, round, opts) => ({ findings: [], confidence: 'high', verificationReceipt: receipt(runDir, round, opts) })
    v = await reviewPanel({ ...base(dir), reviewerSet: ['test-reviewer'] })
    assert.notStrictEqual(v.terminal, 'clean')
    assert.match(v.reason || '', /coverage-decisions/)
  }

  // 15. stale coverage-decision write fails closed and leaves old artifact unchanged.
  {
    const dir = freshDir()
    const path = io().join(dir, 'review-coverage-decisions.json')
    await io().writeFile(path, JSON.stringify([{ id: 'RCD-old', classKey: 'Test::old' }]))
    global.reviewerAgent = async (reviewer, context, rubric, runDir, round, opts) => {
      if (round === 1) return { findings: BLOCKER, confidence: 'high', verificationReceipt: receipt(runDir, round, opts) }
      return { findings: [], confidence: 'high', verificationReceipt: receipt(runDir, round, opts) }
    }
    v = await reviewPanel({ ...base(dir), reviewerSet: ['test-reviewer'], forceCoverageDecisionExpectedHash: 'wrong', fixStep: async () => ({ changedSubjects: ['Test'], coverageDecisions: [{ id: 'RCD-new', classKey: 'Test::new' }] }) })
    assert.notStrictEqual(v.terminal, 'clean')
    assert.deepStrictEqual(JSON.parse(await io().readText(path)), [{ id: 'RCD-old', classKey: 'Test::old' }])
    const records = JSON.parse(await io().readText(io().join(dir, 'round-records.json')))
    assert.ok(!records.some((rec) => rec.confirmationPending === true), 'failed coverage-decision write must not persist a confirmation marker')
  }

  // 16. helper write failure fails closed.
  {
    const dir = freshDir()
    const oldIo = global.io
    const baseIo = io()
    global.io = Object.assign({}, baseIo, { runHelper: async (cmd, args) => String((args || [])[0]).includes('coverage_decisions.py') ? { ok: false, stdout: '{"ok":false,"reason":"forced"}' } : baseIo.runHelper(cmd, args) })
    global.reviewerAgent = async (reviewer, context, rubric, runDir, round, opts) => {
      if (round === 1) return { findings: BLOCKER, confidence: 'high', verificationReceipt: receipt(runDir, round, opts) }
      return { findings: [], confidence: 'high', verificationReceipt: receipt(runDir, round, opts) }
    }
    v = await reviewPanel({ ...base(dir), reviewerSet: ['test-reviewer'], fixStep: async () => ({ changedSubjects: ['Test'], coverageDecisions: [{ id: 'RCD-fail', classKey: 'Test::fail' }] }) })
    global.io = oldIo
    assert.notStrictEqual(v.terminal, 'clean')
  }

  // 17. wrong coverage principle is challenged in a later round and cannot certify.
  {
    const dir = freshDir()
    let challengedContextSeen = false
    global.reviewerAgent = async (reviewer, context, rubric, runDir, round, opts) => {
      if (round === 1) return { findings: BLOCKER, confidence: 'high', verificationReceipt: receipt(runDir, round, opts), usage: { total: 3 } }
      if (JSON.stringify(context || {}).includes('RCD-wrong')) challengedContextSeen = true
      return { findings: [{ dimension: 'Test', taxonomy: 'coverage', title: 'Coverage decision is false', severity: 'Important', classKey: 'Test::coverage::missing acceptance test' }], confidence: 'high', verificationReceipt: receipt(runDir, round, opts), usage: { total: 3 } }
    }
    v = await reviewPanel({ ...base(dir), reviewerSet: ['test-reviewer'], fixStep: async () => ({ changedSubjects: ['Test'], coverageDecisions: [{ id: 'RCD-wrong', classKey: 'Test::coverage::missing acceptance test', text: 'Only happy-path acceptance tests are required.' }] }) })
    assert.ok(challengedContextSeen)
    assert.notStrictEqual(v.terminal, 'clean')
  }

  // 18. a repeated class reaches fixStep as generalizeRequired before a coverage decision is accepted.
  {
    const dir = freshDir()
    const captured = []
    global.reviewerAgent = async (reviewer, context, rubric, runDir, round, opts) => {
      if (round <= 2) return { findings: BLOCKER, confidence: 'high', verificationReceipt: receipt(runDir, round, opts), usage: { total: 3 } }
      return { findings: [], confidence: 'high', verificationReceipt: receipt(runDir, round, opts), usage: { total: 3 } }
    }
    v = await reviewPanel({ ...base(dir), reviewerSet: ['test-reviewer'], fixStep: async (ctx, verdict) => {
      captured.push({ round: verdict.round, ctx })
      if (verdict.round === 1) return { changedSubjects: ['Test'], coverageDecisions: [] }
      return { changedSubjects: ['Test'], coverageDecisions: [{ id: 'RCD-repeat', classKey: 'Test::coverage::missing acceptance test', text: 'Repeated missing acceptance-test class is covered by the new integration fixture.' }] }
    } })
    assert.deepStrictEqual(captured[0].ctx.generalizeRequired || [], [])
    assert.ok((captured.find((x) => x.round === 2).ctx.generalizeRequired || []).some((d) => String(d.classKey).includes('Test::coverage')))
    assert.strictEqual(v.terminal, 'clean')
  }
```

If `showrunner_panel_shell_smoke.js` does not already import it, add `const { io } = require('../io_seam.js')` (adjust the relative path to match the file's existing imports).

Before running the smokes, update existing reviewer stubs in `showrunner_panel_shell_smoke.js` and `showrunner_reviewcode_loop_smoke.js` from legacy arrays or `{findings}`-only objects to the new object shape. Every clean reviewer branch should return `{ findings: [], confidence: 'high', verificationReceipt: receipt(runDir, round, opts), usage: { total: 1 } }`; every blocking branch should return `{ findings: BLOCKER, confidence: 'high', verificationReceipt: receipt(runDir, round, opts), usage: { total: 1 } }`. Update the review-code smoke's `global.agent` reviewer branch the same way so the shell does not treat old smoke stubs as malformed reviewer results.

- [ ] **Step 2: Run failing smoke**

Run: `node plugins/superheroes/lib/tests/showrunner_panel_shell_smoke.js`

Expected: FAIL because `reviewerAgent` still receives no policy options and returns arrays only.

- [ ] **Step 3: Import and use helpers in the shell**

In `plugins/superheroes/lib/review_panel_shell.js`, add imports:

```js
const roundPolicy = require('./review_round_policy.js')
const reviewMemory = require('./review_memory.js')
```

Call Python-only helpers (`review_memory.py`, `coverage_decisions.py`, and `review_telemetry.py`) through the shell's IO seam. Do not add a JavaScript telemetry shim.

In `plugins/superheroes/lib/io_seam.js`, extend `defaultIo` with:

```js
  async runHelper(cmd, args) {
    const cp = require('child_process').spawnSync(cmd, args || [], { encoding: 'utf8' })
    return { ok: cp.status === 0, status: cp.status, stdout: cp.stdout || '', stderr: cp.stderr || '' }
  },
  contentHash(text) {
    return require('crypto').createHash('sha256').update(String(text || ''), 'utf8').digest('hex')
  },
```

Update `plugins/superheroes/lib/bundle_showrunner.js` so the native Workflow `global.io` replacement provides the same `runHelper` and `contentHash` methods through its existing leaf-bash implementation. Add a bundle-preamble smoke or fixture assertion that the generated bundle's `globalThis.io` object exposes both methods before `review_panel_shell.js` can run.

Update `dispatchReviewer` to accept options, preserve the result object, and fail closed on malformed or low-confidence results:

```js
function _validReviewerResult(out) {
  return !!out && Array.isArray(out.findings) && (out.confidence === 'high' || out.confidence === 'low')
}

async function dispatchReviewer(reviewer, context, rubric, runDir, round, roundFindings, opts) {
  const baseOpts = opts || {}
  let out = await reviewerAgent(reviewer, context, rubric, runDir, round, baseOpts)
  if (Array.isArray(out)) out = { findings: out, confidence: 'low', legacyArray: true }
  let escalated = false
  if (baseOpts.tier === 'reviewer' && (!_validReviewerResult(out) || out.confidence !== 'high')) {
    escalated = true
    out = await reviewerAgent(reviewer, context, rubric, runDir, round, Object.assign({}, baseOpts, { tier: 'reviewer-deep', escalatedFrom: 'reviewer' }))
    if (Array.isArray(out)) out = { findings: out, confidence: 'low', legacyArray: true }
  }
  if (!_validReviewerResult(out) || out.confidence !== 'high') {
    roundFindings[reviewer] = { status: 'missing', dimension: reviewer, findings: _validReviewerResult(out) ? out.findings : [], confidence: _validReviewerResult(out) ? out.confidence : 'low', malformed: !_validReviewerResult(out), legacyArray: !!(out && out.legacyArray), escalated }
    return
  }
  roundFindings[reviewer] = Object.assign({ status: 'run', dimension: reviewer, escalated }, out)
}
```

Where the shell builds `roundFindings`, call `roundPolicy.planRound` and dispatch only `action: "run"` dimensions:

```js
    const runId = runKey || runDir
    const lease = legKind && legKind.lease
    let needsConfirmation = !!(lastExtras && lastExtras.needsConfirmation)

    const ioApi = io()
    const memoryState = await loadRoundRecords(runDir, reviewerSet, ioApi)
    const recoveringCorruptMemory = !memoryState.ok
    records = memoryState.ok ? memoryState.records : []
    const latestRecord = records.length ? records[records.length - 1] : null
    needsConfirmation = needsConfirmation || !!(latestRecord && latestRecord.confirmationPending)
    const coverageTarget = await coverageDecisionTarget(runDir, context, legKind, ioApi)
    const coverageState = await loadCoverageDecisions(coverageTarget, ioApi)
    if (!coverageState.ok) return { terminal: 'cannot-certify', reason: 'coverage-decisions-' + (coverageState.state || coverageState.reason || 'unreadable') }
    const coverageDecisions = coverageState.decisions
    const policy = roundPolicy.planRound({
      round,
      dimensions: reviewerSet,
      changedSubjects: recoveringCorruptMemory ? null : (lastExtras && lastExtras.changedSubjects),
      previous: buildPreviousDimensionState(records),
      confirmation: !recoveringCorruptMemory && needsConfirmation,
    })
    const scheduled = policy.dimensions || {}
    const roundFindings = {}
    const receiptContext = { artifact: runId + ':round-' + round, coverageDecisionIds: coverageDecisions.map((d) => d.id).filter(Boolean) }
    await parallel(reviewerSet
      .filter((r) => (scheduled[r] || {}).action !== 'skip')
      .map((r) => () => dispatchReviewer(r, reviewerContext(context, coverageDecisions, receiptContext), rubric, runDir, round, roundFindings, Object.assign({}, scheduled[r], { coverageDecisions, receiptContext, receiptArtifact: receiptContext.artifact }))))
    for (const [name, sched] of Object.entries(scheduled)) {
      if (sched.action === 'skip') roundFindings[name] = carryForwardDimension(records, name, sched)
    }
    const arraysByReviewer = Object.fromEntries(Object.entries(roundFindings).map(([k, v]) => [k, v.findings || []]))
    const synthesized = legKind.panel ? await synthesizeRound(arraysByReviewer, context, rubric, runDir, round) : null
    const tokenUsage = collectRoundUsage(roundFindings, round, synthesized)
    const record = reviewMemory.recordFromDimensionResults(round, policy.roundKind, roundFindings, lastExtras && lastExtras.changedSubjects, coverageDecisions, tokenUsage, needsConfirmation)
    const persisted = await persistRoundRecord(runDir, reviewerSet, record, memoryState.contentHash, runId, lease, ioApi)
    if (!persisted.ok) return { terminal: 'cannot-certify', reason: 'round-memory-write-failed' }
    const recordsForFix = Array.isArray(persisted.records) ? persisted.records : records.concat([record])
    if (recoveringCorruptMemory && wouldOtherwiseCertify(roundFindings, reviewerSet)) return { terminal: 'cannot-certify', reason: 'round-memory-corrupt-recovery' }
```

Add local helpers above `reviewPanel`:

```js
function buildPreviousDimensionState(records) {
  const previous = {}
  for (const rec of records || []) {
    for (const [name, dim] of Object.entries((rec && rec.dimensions) || {})) previous[name] = dim
  }
  return previous
}

function carryForwardDimension(records, name, sched) {
  for (let i = (records || []).length - 1; i >= 0; i -= 1) {
    const dim = records[i].dimensions && records[i].dimensions[name]
    if (dim) return Object.assign({}, dim, { status: 'skipped', carriedFromRound: sched.carriedFromRound })
  }
  return { status: 'skipped', findings: [], confidence: 'low', carriedFromRound: sched.carriedFromRound }
}

function buildFixContext(records, coverageDecisions) {
  const priorFindings = []
  const changedSubjects = []
  for (const rec of records || []) {
    priorFindings.push(...((rec && rec.findings) || []))
    if (Array.isArray(rec && rec.changedSubjects)) changedSubjects.push(...rec.changedSubjects)
  }
  return {
    priorFindings,
    classKeys: priorFindings.map((f) => f.classKey || reviewMemory.classKey(f)),
    generalizeRequired: reviewMemory.recurrentClasses(records, coverageDecisions),
    changedSubjects: Array.from(new Set(changedSubjects)),
    coverageDecisions: coverageDecisions || [],
  }
}

function reviewerContext(context, coverageDecisions, receiptContext) {
  return Object.assign({}, context || {}, { coverageDecisions: coverageDecisions || [], receiptContext })
}

function wouldOtherwiseCertify(roundFindings, reviewerSet) {
  for (const name of reviewerSet || []) {
    const result = roundFindings[name]
    if (!result || result.confidence !== 'high' || (result.findings || []).length > 0) return false
  }
  return true
}
```

Update tally calls so object-shaped dimension results stay object-shaped through terminal decisions. The shell already built `arraysByReviewer` only for synthesis before persisting the round record; do not rebuild `synthesized` later or the record's token usage will miss synthesis usage:

```js
const gateResult = panelTally.roundGateFromDimensionResults(
  roundFindings,
  reviewerSet,
  policy.roundKind === 'confirmation',
  { artifact: runId + ':round-' + round, coverageDecisionIds: coverageDecisions.map((d) => d.id).filter(Boolean) }
)
const compiled = panelTally.compileDimensionResults(roundFindings)
```

Rewrite `tallyRound` to consume `roundFindings` objects, not arrays: `completed` is any reviewer with `status: "run"` or `status: "skipped"`, `compiled` comes from `panelTally.compileDimensionResults(roundFindings)`, and final receipt checks come from `panelTally.roundGateFromDimensionResults(...)`. Preserve each dimension's `confidence`, `verificationReceipt`, `usage`, `carriedFromRound`, and carried-finding metadata until after the terminal decision. Do not use `Array.isArray(roundFindings[r])` as the completion check after this task.

Add shell helpers that use the extended IO seam rather than direct ad hoc writes:

```js
async function loadRoundRecords(runDir, reviewerSet, ioApi) {
  const out = await ioApi.runHelper('python3', ['plugins/superheroes/lib/review_memory.py', 'load', '--path', ioApi.join(runDir, 'round-records.json'), '--dimensions', JSON.stringify(reviewerSet)])
  try {
    const parsed = JSON.parse(out.stdout || '{}')
    return parsed.ok ? parsed : Object.assign({ ok: false }, parsed)
  } catch (_) {
    return { ok: false, reason: 'round-memory-helper-failed' }
  }
}

async function persistRoundRecord(runDir, reviewerSet, record, expectedHash, runId, lease, ioApi) {
  const args = ['plugins/superheroes/lib/review_memory.py', 'persist', '--path', ioApi.join(runDir, 'round-records.json'), '--dimensions', JSON.stringify(reviewerSet), '--record-json', JSON.stringify(record), '--expected-hash', expectedHash || ioApi.contentHash(''), '--run-id', runId]
  if (lease) args.push('--lease', lease)
  const out = await ioApi.runHelper('python3', args)
  return out.ok ? JSON.parse(out.stdout) : { ok: false, reason: 'helper-failed' }
}

async function persistPostFixRecord(runDir, reviewerSet, recordsForFix, round, fixResult, recordedCoverageDecisions, expectedHash, runId, lease, ioApi) {
  const record = Object.assign({}, (recordsForFix || []).find((r) => r && r.round === round) || {})
  record.confirmationPending = true
  record.changedSubjects = fixResult.changedSubjects || []
  record.coverageDecisions = recordedCoverageDecisions || []
  record.fix = { fixes: fixResult.fixes || fixResult.fixed || [], deferred: fixResult.deferred || [] }
  return persistRoundRecord(runDir, reviewerSet, record, expectedHash, runId, lease, ioApi)
}

async function coverageDecisionTarget(runDir, context, legKind, ioApi) {
  if (context && context.docPath) return { mode: 'doc', path: context.docPath }
  const path = (context && context.coverageDecisionPath) || (legKind && legKind.coverageDecisionPath) || ioApi.join(runDir, 'review-coverage-decisions.json')
  return { mode: 'code', path }
}

function parseDocCoverageDecisions(text) {
  const out = []
  const lines = String(text || '').split(/\n/)
  let inSection = false
  for (const line of lines) {
    if (/^##\s+/.test(line)) inSection = line.trim() === '## Review coverage decisions'
    if (!inSection) continue
    const jsonMatch = line.match(/review-coverage-decision-json:(\{.*\})`?$/)
    if (jsonMatch) {
      try { out.push(JSON.parse(jsonMatch[1])); continue } catch (_) {}
    }
    const m = line.match(/^- \*\*([^*]+)\*\* .*class `([^`]+)`\): (.*)$/)
    if (m) out.push({ id: m[1], classKey: m[2], text: m[3] })
  }
  return out
}

async function loadCoverageDecisions(target, ioApi) {
  const path = target.path
  let text = ''
  try { text = await ioApi.readText(path) } catch (err) {
    if (err && err.code === 'ENOENT' && target.mode === 'code') return { ok: true, decisions: [], contentHash: ioApi.contentHash('') }
    return { ok: false, state: 'unreadable', reason: err && err.message }
  }
  if (target.mode === 'doc') return { ok: true, decisions: parseDocCoverageDecisions(text), contentHash: ioApi.contentHash(text) }
  try {
    const decisions = JSON.parse(text || '[]')
    if (!Array.isArray(decisions)) return { ok: false, state: 'corrupt' }
    return { ok: true, decisions, contentHash: ioApi.contentHash(text) }
  } catch (_) {
    return { ok: false, state: 'corrupt' }
  }
}

function collectRoundUsage(roundFindings, round, synthesized) {
  const usage = {}
  for (const [name, result] of Object.entries(roundFindings || {})) {
    if (result && result.usage) usage[`${name}:r${round}`] = result.usage
  }
  if (synthesized && synthesized.usage) usage[`synthesis:r${round}`] = synthesized.usage
  return usage
}

function expectedUsageLeaves(reviewerSet, round, legKind, fixRan) {
  const leaves = (reviewerSet || []).map((name) => `${name}:r${round}`)
  if (legKind && legKind.panel) leaves.push(`synthesis:r${round}`)
  if (legKind && legKind.code) leaves.push(`verify:r${round}`)
  if (fixRan) leaves.push(`fix:r${round}`)
  return leaves
}

function telemetryPayload(records, expectedLeaves, usage, benchmark, terminal) {
  const missing = expectedLeaves.filter((leaf) => !usage[leaf])
  const total = expectedLeaves.reduce((sum, leaf) => sum + Number((usage[leaf] && usage[leaf].total) || 0), 0)
  const dimensionCounts = {}
  for (const rec of records || []) {
    for (const [name, dim] of Object.entries((rec && rec.dimensions) || {})) {
      const counts = dimensionCounts[name] || { run: 0, skipped: 0, cheap: 0, deep: 0, escalated: 0 }
      if (dim.status === 'skipped') counts.skipped += 1
      if (dim.status === 'run') counts.run += 1
      if (dim.tier === 'reviewer') counts.cheap += 1
      if (dim.tier === 'reviewer-deep') counts.deep += 1
      if (dim.escalated) counts.escalated += 1
      dimensionCounts[name] = counts
    }
  }
  return {
    schemaVersion: 1,
    terminal,
    roundCount: (records || []).length,
    rounds: records || [],
    tokenUsage: { complete: missing.length === 0, expectedLeaves, present: expectedLeaves.filter((leaf) => usage[leaf]), missing, total },
    dimensionCounts,
    benchmarkValid: !benchmark || missing.length === 0,
  }
}

async function writeTelemetry(runDir, payload, expectedHash, runId, lease, ioApi) {
  const args = ['plugins/superheroes/lib/review_telemetry.py', 'write', '--path', ioApi.join(runDir, 'review-telemetry.json'), '--payload-json', JSON.stringify(payload), '--expected-hash', expectedHash || ioApi.contentHash(''), '--run-id', runId]
  if (lease) args.push('--lease', lease)
  const out = await ioApi.runHelper('python3', args)
  return out.ok ? JSON.parse(out.stdout) : { ok: false, benchmarkValid: false, reason: 'telemetry-write-failed' }
}

async function recordCoverageDecision(targetPath, decision, expectedHash, mode, runId, lease, ioApi) {
  const cmd = mode === 'code' ? 'record-code' : 'record-doc'
  const args = ['plugins/superheroes/lib/coverage_decisions.py', cmd, '--path', targetPath, '--decision-json', JSON.stringify(decision), '--expected-hash', expectedHash, '--run-id', runId]
  if (lease) args.push('--lease', lease)
  const out = await ioApi.runHelper('python3', args)
  return out.ok ? JSON.parse(out.stdout) : { ok: false, reason: 'coverage-decision-write-failed' }
}
```

After every blocking round, call `fixStep(buildFixContext(recordsForFix, coverageDecisions), verdict, runDir)`, where `recordsForFix` includes the just-persisted current round record. If the fix returns coverage decisions, durably record each decision with `coverage_decisions.py` first, then reload the coverage-decision target and pass the reloaded `recordedCoverageDecisions` into `persistPostFixRecord(runDir, reviewerSet, recordsForFix, round, fixResult, recordedCoverageDecisions, persisted.contentHash, runId, lease, ioApi)`. Only this post-fix record rewrite may set `confirmationPending=true`; it must happen after coverage decisions are visible to later reviewers. If any coverage-decision write, reload, or post-fix record write fails, return `cannot-certify` and do not start another round. On resume, derive `needsConfirmation` from the latest v2 round record's `confirmationPending` field. If that latest record carries coverage decision ids that are not present in the reloaded coverage-decision target, return `cannot-certify` with a `coverage-decision-marker-missing` reason before dispatching confirmation reviewers. Only a successful full confirmation round may clear it with a final record that has `confirmationPending=false`. The policy must enter confirmation mode from shell-owned durable state; `fixStep` does not own that transition. A clean intermediate round after a fix prepares confirmation but does not certify until the subsequent full `reviewer-deep` confirmation round succeeds.

After every `fixStep`, record returned `coverageDecisions` via `coverage_decisions.py` using `coverageDecisionTarget(...)`, that target's expected content hash, `runId`, and lease/session token before setting any post-fix confirmation marker. Doc-review legs use `context.docPath` and `record-doc`; code-review legs use `context.coverageDecisionPath` or `legKind.coverageDecisionPath` and `record-code`. A stale, malformed, unreadable, or failed coverage-decision write returns `cannot-certify`, leaves the old file intact, and must not persist `confirmationPending=true`. Reload recorded coverage decisions from the same target before the post-fix marker and before each later round, include them in reviewer context and `opts.coverageDecisions`, and pass the full fix context to `fixStep`.

Update `runReviewDocPanel` to pass the existing object context with `docPath`. Update `runReviewCodePanel` to pass an object context such as `{ workItem, target, coverageDecisionPath: joinPath(runDir, 'review-coverage-decisions.json') }` instead of a bare work-item string, and update code-review prompts to read `context.workItem || context` for backward compatibility.

Before returning any terminal verdict, build a payload with `expectedUsageLeaves` and `telemetryPayload`, call `writeTelemetry`, then read back `review-telemetry.json` and attach that saved artifact to the verdict/readout record. Preserve the terminal if telemetry writing fails, but attach `{ benchmarkValid: false, reason: 'telemetry-write-failed' }`. A failed or incomplete telemetry write cannot satisfy benchmark acceptance.

Use `panelTally.roundGateFromDimensionResults` for final-confirmation receipt checks, passing the same `receiptContext` given to reviewers. A missing reviewer result, malformed reviewer result, low-confidence result after deep escalation, stale coverage-decision write, or round-memory write failure must not produce `terminal: "clean"`.

Add shell smokes for coverage-decision stale hash, malformed JSON in `review-coverage-decisions.json`, and failed helper writes. Each must return a non-clean terminal and leave the old artifact unchanged. Keep the wrong-principle and repeated-class probes in Step 1 so they fail before this implementation step.

- [ ] **Step 4: Update showrunner reviewer wrappers**

In `plugins/superheroes/lib/showrunner.js`, change `FINDINGS_SCHEMA`:

```js
const FINDINGS_SCHEMA = {
  type: 'object',
  required: ['findings', 'confidence'],
  properties: {
    findings: { type: 'array' },
    confidence: { enum: ['high', 'low'] },
    verificationReceipt: { type: 'object' },
    usage: { type: 'object' },
  },
}
```

Change `SYNTH_VERDICTS_SCHEMA` to allow usage:

```js
const SYNTH_VERDICTS_SCHEMA = {
  type: 'object',
  required: ['verdicts'],
  properties: { verdicts: { type: 'array' }, usage: { type: 'object' } },
}
```

Update every synthesis leaf wrapper to return the full object, and update `synthesizeRound` in `review_panel_shell.js` to preserve that usage:

```js
const leaf = await synthesisLeaf(merged, context, rubric, runDir, round)
const consumed = loopSynthesis.consume(merged, leaf && Array.isArray(leaf.verdicts) ? leaf.verdicts : [])
return Object.assign(consumed, { usage: leaf && leaf.usage })
```

Update the real reviewer wrappers in `plugins/superheroes/lib/showrunner.js`:

```js
// In reviewCodeLeaves(...), change the leaf signature to:
const reviewerAgent = async (reviewer, context, rubric, runDir, round, opts = {}) => {
  const tier = opts.tier || 'reviewer-deep'
  const model = tier === 'reviewer' ? tiers.reviewer : tiers.reviewerDeep
  const promptContext = Object.assign({}, context || {}, {
    roundKind: opts.roundKind,
    coverageDecisions: opts.coverageDecisions || [],
    receiptArtifact: opts.receiptArtifact,
    receiptCoverageDecisionIds: (opts.coverageDecisions || []).map((d) => d.id).filter(Boolean),
  })
  const result = await agent(codeReviewPrompt(reviewer, promptContext, rubric, round), withModel(model, { label: `${reviewer}:r${round}`, schema: FINDINGS_SCHEMA }))
  if (!result || !Array.isArray(result.findings)) return null
  return result
}

// Change docReviewerAgent to the same contract:
async function docReviewerAgent(reviewer, context, rubric, runDir, round, opts = {}) {
  const promptContext = Object.assign({}, context || {}, {
    roundKind: opts.roundKind,
    coverageDecisions: opts.coverageDecisions || [],
    receiptArtifact: opts.receiptArtifact,
    receiptCoverageDecisionIds: (opts.coverageDecisions || []).map((d) => d.id).filter(Boolean),
  })
  const result = await agent(docReviewerPrompt(reviewer, promptContext, rubric, runDir, round), { label: reviewer, schema: FINDINGS_SCHEMA })
  if (!result || !Array.isArray(result.findings)) return null
  return result
}
```

Update code/doc reviewer prompts to request:

```text
Return ONLY this shape: {"findings":[],"confidence":"high","verificationReceipt":{"artifact":"<exact receiptArtifact from prompt context>","chain":[{"step":"citation","evidence":"..."},{"step":"reachability","evidence":"..."},{"step":"missing-check","evidence":"..."},{"step":"tooling","evidence":"..."}],"coverageDecisionIds":["<every id from receiptCoverageDecisionIds>"]},"usage":{"input":0,"output":0,"total":0}}. Replace every placeholder with the actual review result. If a step has no evidence, return {"findings":[],"confidence":"low","usage":{...}} instead of a boilerplate receipt.
```

For legacy/null responses, keep returning `null` so the shell fails closed.

Update the production fixer/reviser wrappers to consume the new `fixStep` context and return the same structured fix result that the shell smokes use. In `plugins/superheroes/lib/showrunner.js`, add:

```js
const FIX_RESULT_SCHEMA = {
  type: 'object',
  required: ['changedSubjects', 'coverageDecisions'],
  properties: {
    fixes: { type: 'array' },
    fixed: { type: 'array' },
    deferred: { type: 'array' },
    changedSubjects: { type: 'array' },
    coverageDecisions: { type: 'array' },
    extras: { type: 'object' },
  },
}

function normalizeFixResult(result) {
  if (!result || !Array.isArray(result.changedSubjects) || !Array.isArray(result.coverageDecisions)) return null
  return Object.assign({}, result, {
    fixes: result.fixes || result.fixed || [],
    extras: Object.assign({}, result.extras || {}, { changedSubjects: result.changedSubjects, needsConfirmation: true }),
  })
}
```

Change the code-review fixer leaf and doc-reviser leaf so their prompt context includes `priorFindings`, `classKeys`, `generalizeRequired`, `changedSubjects`, and `coverageDecisions` from `fixContext`, then validate through `FIX_RESULT_SCHEMA` and `normalizeFixResult`:

```js
async function codeFixerAgent(fixContext, verdict, runDir) {
  const result = await agent(codeFixPrompt(fixContext, verdict), withModel(tiers.fixer, { label: `code-fixer:r${verdict.round}`, schema: FIX_RESULT_SCHEMA }))
  return normalizeFixResult(result)
}

async function docReviserAgent(fixContext, verdict, runDir) {
  const result = await agent(docReviserPrompt(fixContext, verdict), { label: 'doc-reviser', schema: FIX_RESULT_SCHEMA })
  return normalizeFixResult(result)
}
```

Update both fixer prompts to include this exact instruction:

```text
You receive priorFindings, classKeys, generalizeRequired, changedSubjects, and coverageDecisions. Local first occurrences should normally return changedSubjects with no coverageDecisions. When generalizeRequired contains a class you are actually addressing, return a visible coverageDecisions entry with id, classKey, text, and sourceRound. Return ONLY {"fixes":[],"deferred":[],"changedSubjects":[],"coverageDecisions":[],"extras":{}}.
```

- [ ] **Step 5: Run smokes and commit**

Run: `node plugins/superheroes/lib/tests/showrunner_panel_shell_smoke.js`

Expected: PASS.

Run: `node plugins/superheroes/lib/tests/showrunner_reviewcode_loop_smoke.js`

Expected: PASS.

Commit:

```bash
git add plugins/superheroes/lib/review_panel_shell.js plugins/superheroes/lib/showrunner.js plugins/superheroes/lib/io_seam.js plugins/superheroes/lib/bundle_showrunner.js plugins/superheroes/lib/tests/showrunner_panel_shell_smoke.js plugins/superheroes/lib/tests/showrunner_reviewcode_loop_smoke.js
git commit -m "feat(superheroes): wire convergent review panel policy"
```

### Task 8: Update Manual Review Skill Contract

**Files:**
- Modify: `plugins/superheroes/reference/review-loop.md`
- Modify: `plugins/superheroes/skills/review-spec/SKILL.md`
- Modify: `plugins/superheroes/skills/review-plan/SKILL.md`
- Modify: `plugins/superheroes/skills/review-tasks/SKILL.md`
- Modify: `plugins/superheroes/skills/review-code/SKILL.md`
- Create or modify: `plugins/superheroes/lib/tests/test_loop_gate_wired.py`

**Interfaces:**
- Produces: one shared markdown contract for recurrence, dimension skipping, tier cascade, confirmation, telemetry, and coverage decisions.

- [ ] **Step 1: Write failing skill-shape test**

If `plugins/superheroes/lib/tests/test_loop_gate_wired.py` does not exist, create it:

```python
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_review_skills_reference_shared_loop_contract():
    for rel in [
        "skills/review-spec/SKILL.md",
        "skills/review-plan/SKILL.md",
        "skills/review-tasks/SKILL.md",
        "skills/review-code/SKILL.md",
    ]:
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "reference/review-loop.md" in text
        assert "coverage decisions" in text
```

- [ ] **Step 2: Run failing test**

Run: `python3 -m pytest plugins/superheroes/lib/tests/test_loop_gate_wired.py -q`

Expected: FAIL for any review skill that does not reference the shared contract.

- [ ] **Step 3: Update the shared contract**

Append to `plugins/superheroes/reference/review-loop.md`:

```markdown
## Convergent Shared Review Loop

Round 1 is always a full `reviewer-deep` panel. Intermediate rounds may skip only dimensions with a high-confidence clean result whose subject area was not touched; unknown subject impact runs all dimensions. Intermediate run dimensions start at `reviewer` and escalate to `reviewer-deep` whenever the result is missing or low-confidence.

Recurring blocking classes are detected from durable round memory and passed only to the reviser/fix step as `generalizeRequired`. Reviewers never receive prior-round finding lists. Any dismissal or class-covering principle is recorded as a visible coverage decision and is passed to every later reviewer as a challengeable claim.

Certification after any fix requires a full `reviewer-deep` confirmation round with high-confidence clean results and valid verification receipts. A blocking `clean-with-skips`, malformed receipt, stale writer, corrupt memory, or failed coverage-decision write does not pass.

Telemetry records rounds, run/skip/tier counts, per-leaf token usage completeness, and benchmark validity. Telemetry failure does not change the review terminal, but incomplete benchmark telemetry cannot satisfy the cost comparison.
```

- [ ] **Step 4: Point each review skill at the shared contract**

In each of the four skill files, replace repeated convergence-loop prose with:

```markdown
For recurrence handling, coverage decisions, dimension skipping, tier cascade, final confirmation, and telemetry, use `plugins/superheroes/reference/review-loop.md` as the shared loop contract. This skill owns only its leg-specific setup, reviewer framing, and gate-write rules.
```

- [ ] **Step 5: Run validators and commit**

Run: `python3 .github/scripts/validate_skills.py`

Expected: PASS.

Run: `python3 -m pytest plugins/superheroes/lib/tests/test_loop_gate_wired.py -q`

Expected: PASS.

Commit:

```bash
git add plugins/superheroes/reference/review-loop.md plugins/superheroes/skills/review-spec/SKILL.md plugins/superheroes/skills/review-plan/SKILL.md plugins/superheroes/skills/review-tasks/SKILL.md plugins/superheroes/skills/review-code/SKILL.md plugins/superheroes/lib/tests/test_loop_gate_wired.py
git commit -m "docs(superheroes): share convergent review loop contract"
```

### Task 9: Add Acceptance Benchmarks and Fail-Closed Probes

**Files:**
- Create: `plugins/superheroes/eval/review_loop_runner.js`
- Create: `plugins/superheroes/eval/tests/test_review_loop_convergence.py`
- Create: `plugins/superheroes/eval/fixtures/review_loop/plan_120_replay.json`
- Create: `plugins/superheroes/eval/fixtures/review_loop/code_review_recurring_class.json`
- Create: `plugins/superheroes/eval/fixtures/review_loop/wrong_principle.json`
- Create: `plugins/superheroes/eval/fixtures/review_loop/skipped_dimension_regression.json`
- Create: `plugins/superheroes/eval/fixtures/review_loop/resume_memory.json`
- Create: `plugins/superheroes/eval/fixtures/review_loop/telemetry_failure.json`

**Interfaces:**
- Produces: benchmark/probe coverage for #120, second code-review benchmark, wrong principle, skipped regression, resume memory, atomic doc writes, telemetry failure.

- [ ] **Step 1: Write fixture skeletons with concrete expected terminals**

Create `plugins/superheroes/eval/fixtures/review_loop/wrong_principle.json`:

```json
{
  "name": "wrong-principle-final-confirmation",
  "reviewerSet": ["test-reviewer"],
  "fixEvents": [{"afterRound": 1, "changedSubjects": ["Test"], "coverageDecisions": [{"id": "RCD-wrong", "classKey": "Test::coverage::missing acceptance test", "text": "Only happy-path acceptance tests are required."}]}],
  "reviewerEvents": [
    {"round": 1, "reviewer": "test-reviewer", "findings": [{"dimension": "Test", "taxonomy": "coverage", "title": "Missing acceptance test", "severity": "Important"}], "usageTotal": 1000},
    {"round": 2, "reviewer": "test-reviewer", "tier": "reviewer", "findings": [{"dimension": "Test", "taxonomy": "coverage", "title": "Coverage decision is false", "severity": "Important"}], "usageTotal": 1000}
  ],
  "rounds": [
    {"findings": [{"dimension": "Test", "taxonomy": "coverage", "title": "Missing acceptance test", "severity": "Important"}]},
    {"coverageDecision": {"id": "RCD-wrong", "classKey": "Test::coverage::missing acceptance test", "text": "Only happy-path acceptance tests are required."}},
    {"findings": [{"dimension": "Test", "taxonomy": "coverage", "title": "Coverage decision is false", "severity": "Important"}]}
  ],
  "expectedTerminal": "continue",
  "mustNotPass": true
}
```

Create `skipped_dimension_regression.json`:

```json
{
  "name": "skipped-dimension-regression",
  "reviewerSet": ["security-reviewer", "test-reviewer"],
  "fixEvents": [{"afterRound": 1, "changedSubjects": ["Test"], "coverageDecisions": []}],
  "reviewerEvents": [
    {"round": 1, "reviewer": "security-reviewer", "findings": [], "usageTotal": 1000},
    {"round": 1, "reviewer": "test-reviewer", "findings": [{"dimension": "Test", "taxonomy": "coverage", "title": "Missing test", "severity": "Important"}], "usageTotal": 1000},
    {"round": 2, "reviewer": "test-reviewer", "tier": "reviewer", "findings": [], "usageTotal": 1000},
    {"round": 3, "reviewer": "security-reviewer", "tier": "reviewer-deep", "findings": [{"dimension": "Security", "severity": "Important", "title": "Secret leaked in readout"}], "usageTotal": 1000},
    {"round": 3, "reviewer": "test-reviewer", "tier": "reviewer-deep", "findings": [], "usageTotal": 1000}
  ],
  "rounds": [
    {"security": {"confidence": "high", "findings": []}, "test": {"confidence": "high", "findings": [{"severity": "Important", "title": "Missing test"}]}},
    {"changedSubjects": ["Test"], "securitySkipped": true},
    {"confirmationFindings": [{"dimension": "Security", "severity": "Important", "title": "Secret leaked in readout"}]}
  ],
  "expectedTerminal": "continue",
  "mustNotPass": true
}
```

Create `telemetry_failure.json`:

```json
{
  "name": "telemetry-failure-does-not-change-terminal",
  "reviewerSet": ["test-reviewer"],
  "reviewerEvents": [
    {"round": 1, "reviewer": "test-reviewer", "findings": [], "usageTotal": 1000}
  ],
  "baselineTerminal": "clean",
  "telemetryWriteFails": true,
  "missingUsage": ["synthesis:r1"],
  "expectedTerminal": "clean",
  "benchmarkValid": false
}
```

Create `plugins/superheroes/eval/fixtures/review_loop/plan_120_replay.json`:

```json
{
  "name": "plan-120-replay",
  "benchmark": true,
  "maxRounds": 3,
  "reviewerSet": ["architecture-reviewer", "code-reviewer", "premortem-reviewer", "security-reviewer", "test-reviewer"],
  "fixEvents": [
    {"afterRound": 1, "changedSubjects": ["Test"], "coverageDecisions": []},
    {"afterRound": 2, "changedSubjects": ["Test"], "coverageDecisions": [{"id": "RCD-plan-coverage", "classKey": "Test::coverage::missing acceptance test", "text": "Acceptance fixtures cover repeated missing-test findings.", "sourceRound": 2}]}
  ],
  "reviewerEvents": [
    {"round": 1, "reviewer": "architecture-reviewer", "findings": [], "usageTotal": 120000},
    {"round": 1, "reviewer": "code-reviewer", "findings": [], "usageTotal": 120000},
    {"round": 1, "reviewer": "premortem-reviewer", "findings": [], "usageTotal": 120000},
    {"round": 1, "reviewer": "security-reviewer", "findings": [], "usageTotal": 120000},
    {"round": 1, "reviewer": "test-reviewer", "findings": [{"dimension": "Test", "taxonomy": "coverage", "title": "Missing acceptance test", "severity": "Important", "classKey": "Test::coverage::missing acceptance test"}], "usageTotal": 200000},
    {"round": 2, "reviewer": "test-reviewer", "tier": "reviewer", "findings": [{"dimension": "Test", "taxonomy": "coverage", "title": "Missing acceptance test", "severity": "Important", "classKey": "Test::coverage::missing acceptance test"}], "usageTotal": 25000},
    {"round": 3, "reviewer": "architecture-reviewer", "tier": "reviewer-deep", "findings": [], "usageTotal": 100000},
    {"round": 3, "reviewer": "code-reviewer", "tier": "reviewer-deep", "findings": [], "usageTotal": 100000},
    {"round": 3, "reviewer": "premortem-reviewer", "tier": "reviewer-deep", "findings": [], "usageTotal": 100000},
    {"round": 3, "reviewer": "security-reviewer", "tier": "reviewer-deep", "findings": [], "usageTotal": 100000},
    {"round": 3, "reviewer": "test-reviewer", "tier": "reviewer-deep", "findings": [], "usageTotal": 100000}
  ],
  "frozenBaselineTokens": 3500000,
  "expectedTerminal": "clean",
  "requiresCompleteTelemetry": true,
  "expectedCoverageDecision": "RCD-plan-coverage",
  "expectedGeneralizeRequired": "Test::coverage::missing acceptance test",
  "attribution": ["convergence", "skipped-dimensions", "tier-split"]
}
```

Create `plugins/superheroes/eval/fixtures/review_loop/code_review_recurring_class.json`:

```json
{
  "name": "code-review-recurring-class",
  "benchmark": true,
  "maxRounds": 4,
  "fixtureShape": "code review with repeated Test coverage class across source and test files",
  "reviewerSet": ["architecture-reviewer", "code-reviewer", "premortem-reviewer", "security-reviewer", "test-reviewer"],
  "fixEvents": [
    {"afterRound": 1, "changedSubjects": ["Code", "Test"], "coverageDecisions": []},
    {"afterRound": 2, "changedSubjects": ["Test"], "coverageDecisions": [{"id": "RCD-code-test-coverage", "classKey": "Test::coverage::missing regression", "text": "Repeated missing regression-test class is covered by the new regression fixture.", "sourceRound": 2}]}
  ],
  "reviewerEvents": [
    {"round": 1, "reviewer": "architecture-reviewer", "findings": [], "usageTotal": 120000},
    {"round": 1, "reviewer": "code-reviewer", "findings": [{"dimension": "Code", "taxonomy": "correctness", "title": "Patch misses source branch", "severity": "Important", "classKey": "Code::correctness::patch misses source branch"}], "usageTotal": 260000},
    {"round": 1, "reviewer": "premortem-reviewer", "findings": [], "usageTotal": 120000},
    {"round": 1, "reviewer": "security-reviewer", "findings": [], "usageTotal": 120000},
    {"round": 1, "reviewer": "test-reviewer", "findings": [{"dimension": "Test", "taxonomy": "coverage", "title": "Missing regression", "severity": "Important", "classKey": "Test::coverage::missing regression"}], "usageTotal": 260000},
    {"round": 2, "reviewer": "code-reviewer", "tier": "reviewer", "findings": [], "usageTotal": 35000},
    {"round": 2, "reviewer": "test-reviewer", "tier": "reviewer", "findings": [{"dimension": "Test", "taxonomy": "coverage", "title": "Missing regression", "severity": "Important", "classKey": "Test::coverage::missing regression"}], "usageTotal": 35000},
    {"round": 3, "reviewer": "code-reviewer", "tier": "reviewer", "findings": [], "usageTotal": 35000},
    {"round": 3, "reviewer": "test-reviewer", "tier": "reviewer", "findings": [], "usageTotal": 35000},
    {"round": 4, "reviewer": "architecture-reviewer", "tier": "reviewer-deep", "findings": [], "usageTotal": 90000},
    {"round": 4, "reviewer": "code-reviewer", "tier": "reviewer-deep", "findings": [], "usageTotal": 110000},
    {"round": 4, "reviewer": "premortem-reviewer", "tier": "reviewer-deep", "findings": [], "usageTotal": 90000},
    {"round": 4, "reviewer": "security-reviewer", "tier": "reviewer-deep", "findings": [], "usageTotal": 90000},
    {"round": 4, "reviewer": "test-reviewer", "tier": "reviewer-deep", "findings": [], "usageTotal": 110000}
  ],
  "frozenBaselineTokens": 4200000,
  "expectedTerminal": "clean",
  "requiresCompleteTelemetry": true,
  "expectedCoverageDecision": "RCD-code-test-coverage",
  "expectedGeneralizeRequired": "Test::coverage::missing regression"
}
```

Create `plugins/superheroes/eval/fixtures/review_loop/resume_memory.json`:

```json
{
  "name": "resume-memory",
  "reviewerSet": ["test-reviewer"],
  "seedRoundRecords": [{
    "schemaVersion": 2,
    "round": 1,
    "kind": "baseline",
    "dimensions": {"test-reviewer": {"status": "run", "confidence": "high", "findings": [{"dimension": "Test", "taxonomy": "coverage", "title": "Missing acceptance test", "severity": "Important"}], "hasFindings": true, "subjects": ["Test"]}},
    "findings": [{"dimension": "Test", "taxonomy": "coverage", "title": "Missing acceptance test", "severity": "Important"}],
    "changedSubjects": ["Test"],
    "coverageDecisions": [{"id": "RCD-resume", "classKey": "Test::coverage::missing acceptance test"}]
  }],
  "seedCoverageDecisions": [{"id": "RCD-resume", "classKey": "Test::coverage::missing acceptance test"}],
  "reviewerEvents": [
    {"round": 2, "reviewer": "test-reviewer", "tier": "reviewer", "findings": [{"dimension": "Test", "taxonomy": "coverage", "title": "Missing acceptance test", "severity": "Important"}], "usageTotal": 1000}
  ],
  "seededFiles": ["round-records.json", "review-coverage-decisions.json"],
  "expectedFixContext": ["priorFindings", "classKeys", "changedSubjects", "coverageDecision"],
  "corruptStateExpectedPolicy": "full reviewer-deep round",
  "corruptStateMustNotCertify": true,
  "atomicWriteFailureKeepsOldDoc": true
}
```

- [ ] **Step 2: Write failing eval tests**

Create `plugins/superheroes/eval/tests/test_review_loop_convergence.py`:

```python
import json
from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "review_loop"


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_wrong_principle_probe_must_not_pass():
    fixture = load("wrong_principle.json")
    assert fixture["mustNotPass"] is True
    assert fixture["expectedTerminal"] != "clean"


def test_skipped_dimension_regression_probe_must_not_pass():
    fixture = load("skipped_dimension_regression.json")
    assert fixture["mustNotPass"] is True
    assert fixture["expectedTerminal"] != "clean"


def test_telemetry_failure_keeps_terminal_but_not_benchmark_valid():
    fixture = load("telemetry_failure.json")
    assert fixture["expectedTerminal"] == fixture["baselineTerminal"]
    assert fixture["benchmarkValid"] is False


def test_resume_memory_fixture_names_prior_state():
    fixture = load("resume_memory.json")
    assert "round-records.json" in fixture["seededFiles"]
    assert "coverageDecision" in fixture["expectedFixContext"]
```

- [ ] **Step 3: Run eval tests**

Run: `python3 -m pytest plugins/superheroes/eval/tests/test_review_loop_convergence.py -q`

Expected: PASS for fixture contract tests. If an assertion fails, fix the fixture, not the test.

- [ ] **Step 4: Add executable fixture assertions**

Create `plugins/superheroes/eval/review_loop_runner.js`:

```js
#!/usr/bin/env node
const fs = require('fs')
const os = require('os')
const path = require('path')
const { reviewPanel } = require('../lib/review_panel_shell.js')
const { defaultIo } = require('../lib/io_seam.js')

const fixture = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))
const failTelemetry = process.argv.includes('--fail-telemetry')
function receipt(runId, round, opts = {}) {
  return { artifact: `${runId}:round-${round}`, chain: [
    { step: 'citation', evidence: 'fixture cited changed artifact' },
    { step: 'reachability', evidence: 'fixture reached changed path' },
    { step: 'missing-check', evidence: 'fixture checked missing requirements' },
    { step: 'tooling', evidence: 'fixture harness completed' },
  ], coverageDecisionIds: ((opts.coverageDecisions || []).map((d) => d.id).filter(Boolean)) }
}

const events = (fixture.reviewerEvents || []).slice()
const seen = []
const usage = {}
const coverageDecisionIds = []
const fixContexts = []
const fixResults = []

global.parallel = async (thunks) => Promise.all(thunks.map((t) => t()))
global.log = () => {}
global.io = Object.assign({}, defaultIo, {
  async runHelper(cmd, args) {
    if (failTelemetry && String((args || [])[0]).endsWith('review_telemetry.py')) {
      return { ok: false, status: 1, stdout: '{"ok":false,"reason":"forced-telemetry-failure"}\n', stderr: 'forced telemetry failure' }
    }
    return defaultIo.runHelper(cmd, args)
  },
})

global.reviewerAgent = async (reviewer, context, rubric, runDir, round, opts = {}) => {
  const idx = events.findIndex((e) => e.round === round && e.reviewer === reviewer && (!e.tier || e.tier === opts.tier))
  const event = idx >= 0 ? events.splice(idx, 1)[0] : { findings: [], usageTotal: 1 }
  seen.push({ reviewer, round, tier: opts.tier, roundKind: opts.roundKind })
  usage[`${reviewer}:r${round}`] = { total: event.usageTotal || 1 }
  return { findings: event.findings || [], confidence: event.confidence || 'high', verificationReceipt: receipt(fixture.name, round, opts), usage: { total: event.usageTotal || 1 } }
}
global.synthesisLeaf = async (_merged, _context, _rubric, _runDir, round) => {
  usage[`synthesis:r${round}`] = { total: 1 }
  return { verdicts: [], usage: { total: 1 } }
}
global.recordDeferred = async () => {}
global.fixStep = async (fixContext, verdict) => {
  fixContexts.push({ round: verdict.round, context: fixContext })
  usage[`fix:r${verdict.round}`] = { total: 1 }
  const fix = (fixture.fixEvents || []).find((f) => f.afterRound === verdict.round) || { changedSubjects: [], coverageDecisions: [] }
  fixResults.push({ round: verdict.round, coverageDecisionIds: (fix.coverageDecisions || []).map((d) => d.id).filter(Boolean) })
  for (const d of fix.coverageDecisions || []) coverageDecisionIds.push(d.id)
  return { fixed: ['fixture'], changedSubjects: fix.changedSubjects || [], coverageDecisions: fix.coverageDecisions || [], extras: { changedSubjects: fix.changedSubjects || [], needsConfirmation: true } }
}

async function main() {
  const runDir = fs.mkdtempSync(path.join(os.tmpdir(), `${fixture.name}-`))
  if (fixture.seedRoundRecords) fs.writeFileSync(path.join(runDir, 'round-records.json'), JSON.stringify(fixture.seedRoundRecords))
  if (fixture.seedCoverageDecisions) fs.writeFileSync(path.join(runDir, 'review-coverage-decisions.json'), JSON.stringify(fixture.seedCoverageDecisions))
  const verdict = await reviewPanel({
    reviewerSet: fixture.reviewerSet,
    context: { fixture: fixture.name },
    rubric: 'review-loop convergence eval',
    runKey: fixture.name,
    runDir,
    fixStep: global.fixStep,
    legKind: { panel: true, code: false },
  })
  let telemetry = verdict.telemetry || null
  try { telemetry = JSON.parse(fs.readFileSync(path.join(runDir, 'review-telemetry.json'), 'utf8')) } catch (_) {}
  const fallbackTotal = Object.values(usage).reduce((sum, u) => sum + Number(u.total || 0), 0)
  const tokenTotal = telemetry && telemetry.tokenUsage ? telemetry.tokenUsage.total : fallbackTotal
  console.log(JSON.stringify({ terminal: verdict.terminal, roundCount: Math.max(...seen.map((x) => x.round)), tokenTotal, benchmarkValid: !!(telemetry && telemetry.benchmarkValid), telemetry, coverageDecisionIds, seen, fixContexts, fixResults }))
}

main().catch((err) => {
  console.error(err && err.stack ? err.stack : String(err))
  process.exit(1)
})
```

Extend the same Python test file so benchmark fixtures run through `review_loop_runner.js`, while negative probes feed the pure helpers added in Tasks 1-7. Add these imports, helpers, and assertions:

```python
import importlib.util
import subprocess
import tempfile

LIB = Path(__file__).resolve().parents[2] / "lib"
ROOT = Path(__file__).resolve().parents[4]
RUNNER = Path(__file__).resolve().parents[1] / "review_loop_runner.js"


def mod(name):
    spec = importlib.util.spec_from_file_location(name, LIB / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RP = mod("review_round_policy")
RM = mod("review_memory")
PT = mod("panel_tally")
RT = mod("review_telemetry")


RECEIPT = {"artifact": "fixture", "chain": [{"step": "citation", "evidence": "fixture"}, {"step": "reachability", "evidence": "fixture"}, {"step": "missing-check", "evidence": "fixture"}, {"step": "tooling", "evidence": "fixture"}], "coverageDecisionIds": []}


def run_fixture(name, *args):
    proc = subprocess.run(["node", str(RUNNER), str(FIXTURES / name), *args], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    return json.loads(proc.stdout)


def assert_full_confirmation(observed, fixture):
    final_round = max(call["round"] for call in observed["seen"])
    confirmation = [call for call in observed["seen"] if call["round"] == final_round]
    assert sorted(call["reviewer"] for call in confirmation) == sorted(fixture["reviewerSet"])
    assert all(call["roundKind"] == "confirmation" for call in confirmation)
    assert all(call["tier"] == "reviewer-deep" for call in confirmation)
    assert all(fix["round"] < final_round for fix in observed["fixContexts"])


def assert_recurrence_triggers_decision(observed, fixture):
    expected = fixture["expectedGeneralizeRequired"]
    first = next(fix for fix in observed["fixContexts"] if fix["round"] == 1)
    second = next(fix for fix in observed["fixContexts"] if fix["round"] == 2)
    assert not first["context"].get("generalizeRequired")
    assert any(item["classKey"] == expected for item in second["context"].get("generalizeRequired", []))
    first_result = next(result for result in observed["fixResults"] if result["round"] == 1)
    second_result = next(result for result in observed["fixResults"] if result["round"] == 2)
    assert first_result["coverageDecisionIds"] == []
    assert fixture["expectedCoverageDecision"] in second_result["coverageDecisionIds"]


def observe_corrupt_probe(fixture):
    if fixture["name"] == "resume-memory":
        with tempfile.NamedTemporaryFile("w+", encoding="utf-8") as fh:
            fh.write("{corrupt json")
            fh.flush()
            state = RM.load_records_state(fh.name, ["test-reviewer"])
            assert state["ok"] is False
            assert state["state"] == "corrupt"
        policy = RP.plan_round({"round": 2, "dimensions": ["test-reviewer"], "changedSubjects": "malformed", "previous": {}})
        assert policy["dimensions"]["test-reviewer"]["tier"] == "reviewer-deep"
        return {"terminal": PT.round_gate_from_dimension_results({}, ["test-reviewer"], final_confirmation=False)[0], "corruptStateMustNotCertify": True}
    raise AssertionError(f"unhandled fixture {fixture['name']}")


def test_plan_120_replay_reaches_target_round_count():
    fixture = load("plan_120_replay.json")
    observed = run_fixture("plan_120_replay.json")
    assert observed["terminal"] == fixture["expectedTerminal"]
    assert observed["roundCount"] <= fixture["maxRounds"]
    assert observed["benchmarkValid"] is True
    assert observed["telemetry"]["tokenUsage"]["complete"] is True
    assert observed["tokenTotal"] < fixture["frozenBaselineTokens"]
    assert fixture["expectedCoverageDecision"] in observed["coverageDecisionIds"]
    assert_recurrence_triggers_decision(observed, fixture)
    assert_full_confirmation(observed, fixture)


def test_code_review_benchmark_has_own_target_and_decision():
    fixture = load("code_review_recurring_class.json")
    observed = run_fixture("code_review_recurring_class.json")
    assert observed["terminal"] == fixture["expectedTerminal"]
    assert observed["roundCount"] <= fixture["maxRounds"]
    assert observed["benchmarkValid"] is True
    assert observed["telemetry"]["tokenUsage"]["complete"] is True
    assert observed["tokenTotal"] < fixture["frozenBaselineTokens"]
    assert fixture["expectedCoverageDecision"] in observed["coverageDecisionIds"]
    assert_recurrence_triggers_decision(observed, fixture)
    assert_full_confirmation(observed, fixture)


def test_resume_memory_corrupt_state_cannot_certify():
    fixture = load("resume_memory.json")
    observed = observe_corrupt_probe(fixture)
    assert observed["corruptStateMustNotCertify"] is True
    assert observed["terminal"] != "clean"


def test_resume_memory_restores_fix_context():
    observed = run_fixture("resume_memory.json")
    ctx = observed["fixContexts"][0]["context"]
    assert ctx["priorFindings"]
    assert any("Test::coverage" in key for key in ctx["classKeys"])
    assert "generalizeRequired" in ctx
    assert "Test" in ctx["changedSubjects"]
    assert any(d["id"] == "RCD-resume" for d in ctx["coverageDecisions"])


def test_telemetry_failure_keeps_terminal_but_not_benchmark_valid_in_shell():
    fixture = load("telemetry_failure.json")
    normal = run_fixture("telemetry_failure.json")
    failed = run_fixture("telemetry_failure.json", "--fail-telemetry")
    assert failed["terminal"] == normal["terminal"] == fixture["expectedTerminal"]
    assert failed["benchmarkValid"] is False


def test_wrong_principle_probe_uses_shell_runner():
    observed = run_fixture("wrong_principle.json")
    assert observed["terminal"] != "clean"
    assert "RCD-wrong" in observed["coverageDecisionIds"]


def test_skipped_dimension_regression_uses_shell_runner():
    observed = run_fixture("skipped_dimension_regression.json")
    assert observed["terminal"] != "clean"
    assert any(call["reviewer"] == "security-reviewer" and call["roundKind"] == "confirmation" for call in observed["seen"])
```

- [ ] **Step 5: Run and commit**

Run: `python3 -m pytest plugins/superheroes/eval/tests/test_review_loop_convergence.py -q`

Expected: PASS.

Commit:

```bash
git add plugins/superheroes/eval/review_loop_runner.js plugins/superheroes/eval/tests/test_review_loop_convergence.py plugins/superheroes/eval/fixtures/review_loop
git commit -m "test(superheroes): add convergent review loop probes"
```

### Task 10: Fence Gate, Readout, and Telemetry Mirror Writes

**Files:**
- Modify: `plugins/superheroes/lib/definition_doc.py`
- Modify: `plugins/superheroes/lib/gate_write.py`
- Modify: `plugins/superheroes/lib/showrunner.js`
- Create: `plugins/superheroes/lib/fenced_json.py`
- Create: `plugins/superheroes/lib/fenced_json.js`
- Modify: `plugins/superheroes/lib/bundle_showrunner.js`
- Modify existing tests and skill/helper callers that invoke `definition_doc.py set-gate` directly.
- Modify: `plugins/superheroes/skills/review-spec/SKILL.md`
- Modify: `plugins/superheroes/skills/review-plan/SKILL.md`
- Modify: `plugins/superheroes/skills/review-tasks/SKILL.md`
- Create: `plugins/superheroes/lib/tests/test_gate_write_fencing.py`
- Create: `plugins/superheroes/lib/tests/test_gate_write_callers.py`
- Create: `plugins/superheroes/lib/tests/test_fenced_json.py`
- Create or modify: `plugins/superheroes/lib/tests/showrunner_readout_fencing_smoke.js`
- Modify: `plugins/superheroes/lib/tests/showrunner_fronthalf_phase_smoke.js`

**Interfaces:**
- Produces: one fenced write contract for Workhorse-visible gate records, terminal readouts, and telemetry mirrors.
- Requires: run/session identity, lease or content-hash CAS, same-directory temp write, fsync, `os.replace`, and no write on stale/unreadable state.

- [ ] **Step 1: Add failing fenced-write tests**

Create `plugins/superheroes/lib/tests/test_gate_write_fencing.py`:

```python
import importlib.util
import os

LIB = os.path.join(os.path.dirname(__file__), "..")


def load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(LIB, f"{name}.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


DD = load("definition_doc")


def test_stale_gate_write_refuses_to_touch_doc(tmp_path):
    doc = tmp_path / "tasks.md"
    doc.write_text("---\ngates:\n  review: changes-requested\n---\nbody\n", encoding="utf-8")
    result = DD.set_gate(str(doc), "passed", expected_hash="wrong", run_id="run-new")
    assert result == {"ok": False, "reason": "stale"}
    assert "changes-requested" in doc.read_text(encoding="utf-8")


def test_failed_gate_replace_leaves_old_doc(tmp_path, monkeypatch):
    doc = tmp_path / "plan.md"
    doc.write_text("---\ngates:\n  review: changes-requested\n---\nbody\n", encoding="utf-8")
    before = DD.content_hash(doc.read_text(encoding="utf-8"))
    monkeypatch.setattr(DD.os, "replace", lambda _src, _dst: (_ for _ in ()).throw(OSError("disk full")))
    result = DD.set_gate(str(doc), "passed", expected_hash=before, run_id="run-new")
    assert result["ok"] is False
    assert result["reason"] == "replace-failed"
    assert "changes-requested" in doc.read_text(encoding="utf-8")


def test_doc_changed_after_review_snapshot_does_not_pass(tmp_path):
    doc = tmp_path / "tasks.md"
    doc.write_text("---\ngates:\n  review: changes-requested\n---\nreviewed\n", encoding="utf-8")
    reviewed_hash = DD.content_hash(doc.read_text(encoding="utf-8"))
    doc.write_text("---\ngates:\n  review: changes-requested\n---\nchanged after review\n", encoding="utf-8")
    result = DD.set_gate(str(doc), "passed", expected_hash=reviewed_hash, run_id="run-reviewed")
    assert result == {"ok": False, "reason": "stale"}
    assert "passed" not in doc.read_text(encoding="utf-8")
```

Create `plugins/superheroes/lib/tests/test_gate_write_callers.py`:

```python
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_review_skills_pass_reviewed_snapshot_identity_to_gate_write():
    for rel in [
        "skills/review-spec/SKILL.md",
        "skills/review-plan/SKILL.md",
        "skills/review-tasks/SKILL.md",
    ]:
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "REVIEWED_HASH" in text
        assert "RUN_ID" in text
        assert "--expected-hash" in text
        assert "--run-id" in text


def test_showrunner_direct_gate_path_passes_fence_args():
    text = (ROOT / "lib" / "showrunner.js").read_text(encoding="utf-8")
    review_doc = text[text.index("async function reviewDocPhase"):text.index("module.exports.producePhase")]
    assert "--expected-hash" in review_doc
    assert "--run-id" in review_doc
    assert "--lease" in review_doc
```

Create `plugins/superheroes/lib/tests/showrunner_readout_fencing_smoke.js`:

```js
const assert = require('assert')
const { io } = require('../io_seam.js')
const { fencedJsonWrite } = require('../fenced_json.js')

async function main() {
  const dir = io().join(io().tmpdir(), `readout-fence-${Date.now()}`)
  await io().mkdirp(dir)
  for (const name of ['terminal-record.json', 'front-half-outcome.json', 'telemetry-mirror.json']) {
    const path = io().join(dir, name)
    await io().writeFile(path, JSON.stringify({ runId: 'newer', terminal: 'clean' }))
    const stale = await fencedJsonWrite(path, { runId: 'older', terminal: 'clean' }, { expectedHash: 'wrong', runId: 'older' })
    assert.strictEqual(stale.ok, false)
    const kept = JSON.parse(await io().readText(path))
    assert.strictEqual(kept.runId, 'newer')
  }
}

main().then(() => console.log('ok: readout fencing'))
```

In `plugins/superheroes/lib/tests/showrunner_fronthalf_phase_smoke.js`, add these smoke branches after the existing clean gate-write branch:

```js
  // (f) direct reviewDocPhase gate writes include the reviewed snapshot hash, run id, and lease.
  clean('wi-f')
  const execPrompts = []
  ag = makeAgent({ gate: 'pending', reviewerFindings: [] })
  global.agent = async (prompt, opts) => {
    if ((opts && opts.label) === 'exec') execPrompts.push(prompt)
    return ag(prompt, opts)
  }
  r = await sr.reviewDocPhase('plan', 'wi-f', { runId: 'run-f', lease: 'lease-f', reviewedHash: 'hash-f' })
  const gatePrompt = execPrompts.find((p) => p.includes('set-gate') || p.includes('gate_write.py'))
  assert.ok(gatePrompt, 'reviewDocPhase emitted a gate write command')
  assert.match(gatePrompt, /--expected-hash ['"]?hash-f['"]?/)
  assert.match(gatePrompt, /--run-id ['"]?run-f['"]?/)
  assert.match(gatePrompt, /--lease ['"]?lease-f['"]?/)
  assert.strictEqual(r.phaseResult.confidence, 'high')

  // (g) stale reviewed hash parks and leaves the already-recorded gate unchanged.
  clean('wi-g')
  ag = makeAgent({ gate: 'changes-requested', reviewerFindings: [], setGateFails: true })
  global.agent = ag
  r = await sr.reviewDocPhase('plan', 'wi-g', { runId: 'run-g', lease: 'lease-g', reviewedHash: 'stale-hash' })
  assert.strictEqual(r.gate, 'passed', 'terminal still maps to passed before persistence')
  assert.strictEqual(r.phaseResult.confidence, 'low', 'stale/failed gate write parks instead of advancing')
```

- [ ] **Step 2: Run failing tests**

Run: `python3 -m pytest plugins/superheroes/lib/tests/test_gate_write_fencing.py -q`

Expected: FAIL because `definition_doc.set_gate` has no fenced/atomic write contract yet.

Create `plugins/superheroes/lib/tests/test_fenced_json.py`:

```python
import importlib.util
import json
import os

LIB = os.path.join(os.path.dirname(__file__), "..")


def load():
    spec = importlib.util.spec_from_file_location("fenced_json", os.path.join(LIB, "fenced_json.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


FJ = load()


def test_stale_hash_leaves_existing_json_unchanged(tmp_path):
    path = tmp_path / "terminal-record.json"
    path.write_text('{"runId":"newer","terminal":"clean"}\n', encoding="utf-8")
    result = FJ.write_record(str(path), {"terminal": "clean"}, expected_hash="wrong", run_id="older")
    assert result == {"ok": False, "reason": "stale"}
    assert json.loads(path.read_text(encoding="utf-8"))["runId"] == "newer"


def test_missing_run_id_does_not_write(tmp_path):
    path = tmp_path / "front-half-outcome.json"
    path.write_text('{"runId":"old","gate":"changes-requested"}\n', encoding="utf-8")
    before = FJ.content_hash(path.read_text(encoding="utf-8"))
    result = FJ.write_record(str(path), {"gate": "passed"}, expected_hash=before, run_id=None)
    assert result == {"ok": False, "reason": "missing-run-id"}
    assert json.loads(path.read_text(encoding="utf-8"))["gate"] == "changes-requested"


def test_missing_expected_hash_does_not_self_satisfy_cas(tmp_path):
    path = tmp_path / "terminal-record.json"
    path.write_text('{"runId":"old","terminal":"halt"}\n', encoding="utf-8")
    result = FJ.write_record(str(path), {"terminal": "clean"}, expected_hash=None, run_id="run-new")
    assert result == {"ok": False, "reason": "missing-expected-hash"}
    assert json.loads(path.read_text(encoding="utf-8"))["terminal"] == "halt"


def test_unreadable_current_artifact_leaves_existing_json_unchanged(tmp_path, monkeypatch):
    path = tmp_path / "telemetry-mirror.json"
    path.write_text('{"runId":"old","benchmarkValid":false}\n', encoding="utf-8")
    real_open = FJ.open
    def raising_open(name, *args, **kwargs):
        if os.fspath(name) == os.fspath(path) and "r" in (args[0] if args else kwargs.get("mode", "r")):
            raise OSError("permission denied")
        return real_open(name, *args, **kwargs)
    monkeypatch.setattr(FJ, "open", raising_open)
    result = FJ.write_record(str(path), {"benchmarkValid": True}, expected_hash="ignored", run_id="run-new")
    assert result == {"ok": False, "reason": "unreadable"}
    monkeypatch.setattr(FJ, "open", real_open)
    assert json.loads(path.read_text(encoding="utf-8"))["benchmarkValid"] is False


def test_failed_replace_leaves_existing_json_unchanged(tmp_path, monkeypatch):
    path = tmp_path / "terminal-record.json"
    path.write_text('{"runId":"old","terminal":"halt"}\n', encoding="utf-8")
    before = FJ.content_hash(path.read_text(encoding="utf-8"))
    monkeypatch.setattr(FJ.os, "replace", lambda _src, _dst: (_ for _ in ()).throw(OSError("disk full")))
    result = FJ.write_record(str(path), {"terminal": "clean"}, expected_hash=before, run_id="run-new")
    assert result["ok"] is False
    assert result["reason"] == "replace-failed"
    assert json.loads(path.read_text(encoding="utf-8"))["terminal"] == "halt"
```

Run: `python3 -m pytest plugins/superheroes/lib/tests/test_fenced_json.py -q`

Expected: FAIL because `fenced_json.py` does not exist.

Run: `python3 -m pytest plugins/superheroes/lib/tests/test_gate_write_callers.py -q`

Expected: FAIL until showrunner and manual review skills pass the reviewed snapshot hash and run identity into gate writes.

Run: `node plugins/superheroes/lib/tests/showrunner_readout_fencing_smoke.js`

Expected: FAIL because the fenced JSON write helper is missing.

Run: `node plugins/superheroes/lib/tests/showrunner_fronthalf_phase_smoke.js`

Expected: FAIL until the Workhorse review-doc gate path passes the reviewed snapshot hash and run identity.

- [ ] **Step 3: Implement fenced gate writes**

In `plugins/superheroes/lib/definition_doc.py`, add `content_hash(text)` and make the low-level doc write path use:

```python
def _atomic_replace(path, text):
    directory = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp = tempfile.mkstemp(prefix=".definition-doc-", dir=directory, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
        return {"ok": True}
    except OSError as exc:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        return {"ok": False, "reason": "replace-failed", "detail": str(exc)}
```

Use one API shape everywhere: `set_gate(path, review, *, expected_hash, run_id, lease=None)`. Extend the CLI path used by `gate_write.py` with matching `--expected-hash`, `--run-id`, and optional `--lease` flags. The `expected_hash` must be the content hash captured for the artifact snapshot that was actually reviewed, not a hash recomputed at gate-write time. If `run_id` is missing, return `{"ok": False, "reason": "missing-run-id"}`. If the current content hash does not match `expected_hash`, return `{"ok": False, "reason": "stale"}` and do not write. When the write succeeds, include the run/session identity in the gate journal metadata without changing the public `gates.review` value.

Update `plugins/superheroes/lib/gate_write.py` to receive the reviewed snapshot hash from the review session and pass that hash, `--run-id`, and `--lease` into `definition_doc.py set-gate`. Stale/unreadable gate writes must return `recorded:stale` or non-zero and must not advance the phase.

Update every direct `definition_doc.py set-gate` caller, especially `reviewDocPhase` / `persistPhase` in `plugins/superheroes/lib/showrunner.js` and front-half architect skill helper paths, to pass the reviewed snapshot hash plus run/session identity or route through `gate_write.py`. Update existing definition-doc/gate tests for the new API, preserving an explicit manual/session path for owner-approved manual gates that still supplies a `run_id` such as `manual:<timestamp>`.

Update `plugins/superheroes/skills/review-spec/SKILL.md`, `plugins/superheroes/skills/review-plan/SKILL.md`, and `plugins/superheroes/skills/review-tasks/SKILL.md` so each review session captures the reviewed artifact hash immediately after copying the doc into `$SESSION_DIR` and before dispatching reviewers:

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
RUN_ID="review-${WORK_ITEM}-${SESSION_DIR##*/}"
REVIEWED_HASH=$(python3 "$ROOT_DIR/lib/definition_doc.py" content-hash --path "$SESSION_DIR/$DOC.md")
LEASE="${SESSION_DIR##*/}"
```

Use the leg's actual stable copy filename for `$DOC.md` (`spec.md`, `plan.md`, or `tasks.md`). If `content-hash` is unavailable, call the same library helper in a short Python one-liner that imports `definition_doc.content_hash` and reads the stable copy. Then pass those values to the gate helper:

```bash
GATE=$(python3 "$ROOT_DIR/lib/gate_write.py" --mode certify --doc "$DOC" \
  --work-item "$WORK_ITEM" --reviewed-path "$TARGET_PATH" --review "$REVIEW" \
  --parent-doc "$PARENT_DOC" --root "$ROOT" \
  --expected-hash "$REVIEWED_HASH" --run-id "$RUN_ID" --lease "$LEASE")
```

Do not recompute `REVIEWED_HASH` from `$TARGET_PATH` at gate-write time. If `$TARGET_PATH` changed after the stable copy was reviewed, the helper must report stale/failed and the skill must surface that the reviewed document changed before certification.

- [ ] **Step 4: Fence readout and telemetry mirror writes**

Create `plugins/superheroes/lib/fenced_json.py` with the same content-hash/run-id/lease checks and same-directory temp/fsync/`os.replace` behavior, exposing:

```bash
python3 plugins/superheroes/lib/fenced_json.py write --path <path> --payload-json <json> --expected-hash <hash> --run-id <id> [--lease <lease>]
```

Use this implementation:

```python
#!/usr/bin/env python3
"""Fenced JSON writes for Workhorse-visible readouts and mirrors."""
import argparse
import builtins
import hashlib
import json
import os
import tempfile

open = builtins.open


def content_hash(text):
    return hashlib.sha256(str(text or "").encode("utf-8")).hexdigest()


def _current(path):
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        return {"ok": True, "text": text, "hash": content_hash(text)}
    except FileNotFoundError:
        return {"ok": True, "text": "", "hash": content_hash("")}
    except OSError as exc:
        return {"ok": False, "reason": "unreadable", "detail": str(exc)}


def _atomic_replace(path, text):
    directory = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".fenced-json-", dir=directory, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
        return {"ok": True}
    except OSError as exc:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        return {"ok": False, "reason": "replace-failed", "detail": str(exc)}


def write_record(path, payload, expected_hash=None, run_id=None, lease=None):
    if not run_id:
        return {"ok": False, "reason": "missing-run-id"}
    if not expected_hash:
        return {"ok": False, "reason": "missing-expected-hash"}
    state = _current(path)
    if not state.get("ok"):
        return {"ok": False, "reason": state.get("reason", "unreadable")}
    if state["hash"] != expected_hash:
        return {"ok": False, "reason": "stale"}
    record = dict(payload or {})
    record["runId"] = run_id
    if lease:
        record["lease"] = lease
    result = _atomic_replace(path, json.dumps(record, indent=2, sort_keys=True) + "\n")
    if not result.get("ok"):
        return result
    return {"ok": True, "contentHash": content_hash(json.dumps(record, indent=2, sort_keys=True) + "\n")}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("cmd", choices=["write"])
    parser.add_argument("--path", required=True)
    parser.add_argument("--payload-json", required=True)
    parser.add_argument("--expected-hash")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--lease")
    args = parser.parse_args(argv)
    payload = json.loads(args.payload_json)
    result = write_record(args.path, payload, expected_hash=args.expected_hash, run_id=args.run_id, lease=args.lease)
    print(json.dumps(result))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

Then create `plugins/superheroes/lib/fenced_json.js`:

```js
const { io } = require('./io_seam.js')

async function fencedJsonWrite(path, payload, opts) {
  const ioApi = io()
  if (!opts || !opts.expectedHash) return { ok: false, reason: 'missing-expected-hash' }
  let current = ''
  try { current = await ioApi.readText(path) } catch (err) {
    if (!(err && err.code === 'ENOENT')) return { ok: false, reason: 'unreadable' }
  }
  if (ioApi.contentHash(current) !== opts.expectedHash) return { ok: false, reason: 'stale' }
  if (!opts.runId) return { ok: false, reason: 'missing-run-id' }
  const next = Object.assign({}, payload || {}, { runId: opts.runId, lease: opts.lease })
  const args = ['plugins/superheroes/lib/fenced_json.py', 'write', '--path', path, '--payload-json', JSON.stringify(next), '--expected-hash', opts.expectedHash, '--run-id', opts.runId]
  if (opts.lease) args.push('--lease', opts.lease)
  const out = await ioApi.runHelper('python3', args)
  return out.ok ? JSON.parse(out.stdout) : { ok: false, reason: 'write-failed' }
}

module.exports = { fencedJsonWrite }
```

Import `{ fencedJsonWrite }` in `showrunner.js` and use it for `terminal-record.json`, front-half run outcome JSON, and any telemetry mirror outside the run-local `review-telemetry.json`. Each caller must read the artifact and capture its expected hash before computing the replacement payload, then pass that caller-held hash into `fencedJsonWrite`; missing `expectedHash`, stale, unreadable, or failed readout/mirror writes must park low-confidence and name the stale artifact instead of silently continuing.

Add `fenced_json.js` to `plugins/superheroes/lib/bundle_showrunner.js` before `showrunner.js` so the Workflow bundle can import it.

- [ ] **Step 5: Run tests and commit**

Run: `python3 -m pytest plugins/superheroes/lib/tests/test_gate_write_fencing.py plugins/superheroes/lib/tests/test_fenced_json.py plugins/superheroes/lib/tests/test_gate_write_callers.py -q`

Expected: PASS.

Run: `node plugins/superheroes/lib/tests/showrunner_readout_fencing_smoke.js`

Expected: PASS and output includes `ok: readout fencing`.

Run: `node plugins/superheroes/lib/tests/showrunner_fronthalf_phase_smoke.js`

Expected: PASS.

Commit:

```bash
git add plugins/superheroes/lib/definition_doc.py plugins/superheroes/lib/gate_write.py plugins/superheroes/lib/fenced_json.py plugins/superheroes/lib/fenced_json.js plugins/superheroes/lib/showrunner.js plugins/superheroes/lib/bundle_showrunner.js plugins/superheroes/skills/review-spec/SKILL.md plugins/superheroes/skills/review-plan/SKILL.md plugins/superheroes/skills/review-tasks/SKILL.md plugins/superheroes/lib/tests/test_gate_write_fencing.py plugins/superheroes/lib/tests/test_gate_write_callers.py plugins/superheroes/lib/tests/test_fenced_json.py plugins/superheroes/lib/tests/showrunner_readout_fencing_smoke.js plugins/superheroes/lib/tests/showrunner_fronthalf_phase_smoke.js
git commit -m "fix(superheroes): fence review gate and readout writes"
```

### Task 11: Regenerate Bundle and Run Full Verification

**Files:**
- Modify: `plugins/superheroes/lib/showrunner.bundle.js`

**Interfaces:**
- Produces: bundled showrunner containing new JS twins and shell wiring.

- [ ] **Step 1: Regenerate bundle**

Run: `node plugins/superheroes/lib/bundle_showrunner.js --write`

Expected: output starts with `wrote plugins/superheroes/lib/showrunner.bundle.js`.

- [ ] **Step 2: Run bundle check**

Run: `node plugins/superheroes/lib/bundle_showrunner.js --check`

Expected: `bundle up to date`.

- [ ] **Step 3: Run targeted smokes**

Run: `node plugins/superheroes/lib/tests/showrunner_panel_shell_smoke.js`

Expected: `ok: in-memory loop shell`.

Run: `node plugins/superheroes/lib/tests/showrunner_reviewcode_loop_smoke.js`

Expected: `ok: reviewCodePhase`.

Run: `node plugins/superheroes/lib/tests/showrunner_readout_fencing_smoke.js`

Expected: `ok: readout fencing`.

- [ ] **Step 4: Run full repo verification**

Run:

```bash
python3 .github/scripts/validate_marketplace.py
python3 .github/scripts/validate_hosts.py
python3 .github/scripts/validate_skills.py
python3 -m pytest .github/scripts/tests/ plugins/superheroes/lib/tests/ plugins/superheroes/eval/tests/ eval/lib/tests/ -q
```

Expected: all validators pass and pytest exits with code 0.

- [ ] **Step 5: Commit final generated bundle**

Commit:

```bash
git add plugins/superheroes/lib/showrunner.bundle.js
git commit -m "chore(superheroes): regenerate showrunner bundle"
```

### Task 12: Final Build Readiness Check

**Files:**
- Verify only; no planned file edits.

**Interfaces:**
- Produces: ready-for-review branch state for Workhorse's review/code/test-pilot phases.

- [ ] **Step 1: Inspect commit stack**

Run: `git log --oneline --max-count=12`

Expected: commits from Tasks 1-11 appear on top of the workhorse branch.

- [ ] **Step 2: Confirm no unintended docs/store changes are staged**

Run: `git status --short`

Expected: no unstaged or staged changes.

- [ ] **Step 3: Confirm gates remain source-of-truth**

Run:

```bash
ROOT=$(git rev-parse --show-toplevel)
python3 /path/to/home/.codex/plugins/cache/superheroes/superheroes/0.3.0/lib/definition_doc.py read-gate --doc tasks --work-item make-the-shared-review-and-fix-loop-converge-faste-4c45d8 --root "$ROOT"
```

Expected before Build starts: `passed`.

- [ ] **Step 4: Stop at Workhorse boundary**

Do not run Build from this Tasks phase. Hand off to `superheroes:workhorse` with the approved tasks doc path and work item slug.
