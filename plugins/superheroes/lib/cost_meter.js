// plugins/superheroes/lib/cost_meter.js
// #130 token telemetry — a per-run, in-memory cost accumulator shared across the bundled spine via
// globalThis.__SR_COST. The bundle's agent wrapper calls record() on EVERY dispatch (the single
// choke-point) to tally the proxy — dispatch count × resolved model tier — under the current phase
// (globalThis.__SR_PHASE). runPhases calls mark(phase) at the phase boundary to baseline the output-
// token cursor; the phase's persist leaf calls take(phase) to snapshot the proxy counts + the budget-
// derived output-token delta, folded into the SAME durable write (no new leaf — #118). Pure +
// injectable: all state under globalThis; the budget is read via globalThis.__SR_BUDGET (bound by the
// preamble, injectable in tests). Never throws.

function _g() { return (typeof globalThis !== 'undefined') ? globalThis : {} }

function _state() {
  var g = _g()
  if (!g.__SR_COST || typeof g.__SR_COST !== 'object') g.__SR_COST = { phases: {}, starts: {} }
  if (!g.__SR_COST.starts) g.__SR_COST.starts = {}
  return g.__SR_COST
}

// record(model): count one dispatch under the current phase, keyed by the resolved model. The phase's
// OWN persist leaf (which writes the folded phase_cost) is excluded by ORDERING, not a flag: take()
// snapshots-and-resets the phase before that leaf dispatches, so the persist dispatch lands in a
// freshly-reset bucket that is never emitted (documented as an inherent exclusion in CONVENTIONS §4.6).
function record(model) {
  var s = _state()
  var phase = _g().__SR_PHASE || 'unknown'
  var p = s.phases[phase] || (s.phases[phase] = { dispatches: 0, byModel: {} })
  p.dispatches += 1
  var key = model || 'unknown'
  p.byModel[key] = (p.byModel[key] || 0) + 1
}

// readSpent(): the Workflow budget's cumulative OUTPUT-token cursor, or null when the runtime does
// not surface it (deterministic smokes, non-Workflow contexts). Guarded — never throws.
function readSpent() {
  var b = _g().__SR_BUDGET
  if (b && typeof b.spent === 'function') {
    try {
      var v = b.spent()
      return (typeof v === 'number' && isFinite(v)) ? v : null
    } catch (_) { return null }
  }
  return null
}

// mark(phase): baseline the output-token cursor at the phase boundary. take(phase) diffs against it.
function mark(phase) { _state().starts[phase] = readSpent() }

// take(phase): snapshot + RESET this phase's proxy counts, and compute the measured output-token
// delta since the phase's mark() (both endpoints must be finite numbers to count as measured).
// Returns the phase_cost payload body. Never throws.
function take(phase) {
  var s = _state()
  var p = s.phases[phase] || { dispatches: 0, byModel: {} }
  delete s.phases[phase]
  var startSpent = s.starts[phase]
  delete s.starts[phase]
  var endSpent = readSpent()
  var output = null, measured = false
  if (typeof startSpent === 'number' && isFinite(startSpent) &&
      typeof endSpent === 'number' && isFinite(endSpent)) {
    output = Math.max(0, endSpent - startSpent)
    measured = true
  }
  return {
    phase: phase,
    dispatches: { total: p.dispatches, byModel: p.byModel },
    tokens: { output: output, input: null, measured: measured, source: measured ? 'budget' : 'none' },
  }
}

// isEmpty(body): a phase with no dispatches AND no measured tokens — nothing worth recording.
function isEmpty(body) {
  return !!body && !body.dispatches.total && !body.tokens.measured
}

// reset(): clear all accumulated state (new-run guard / test helper).
function reset() { _g().__SR_COST = { phases: {}, starts: {} } }

module.exports = { record: record, readSpent: readSpent, mark: mark, take: take, isEmpty: isEmpty, reset: reset }
