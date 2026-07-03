// Regression (#157 follow-up): transport-failed rounds (all dimensions missing) must not seed
// the no-net-progress breaker. Run wf_09c036a1-242: 0 → 3 → 3 was a bogus halt — the leading 0
// was a schema-400 corpse round where no reviewer ran.
'use strict'
const assert = require('assert')
const { checkCircuitBreaker } = require('../circuit_breaker.js')

const REVIEWERS = [
  'architecture-reviewer', 'code-reviewer', 'security-reviewer',
  'test-reviewer', 'premortem-reviewer',
]

function allMissingDims() {
  const dims = {}
  for (const r of REVIEWERS) dims[r] = { status: 'missing', findings: [], confidence: 'low' }
  return dims
}

function allRunDims() {
  const dims = {}
  for (const r of REVIEWERS) dims[r] = { status: 'run', findings: [], confidence: 'high' }
  return dims
}

function blocking3(suffix) {
  return [
    { file: 'plugins/superheroes/lib/acceptance_run.py', title: `layering ${suffix}`, severity: 'Important', dimension: 'Architecture' },
    { file: 'plugins/superheroes/lib/acceptance_deps.py', title: `deps ${suffix}`, severity: 'Critical', dimension: 'Security' },
    { file: 'plugins/superheroes/lib/acceptance_launch.py', title: `launch ${suffix}`, severity: 'Important', dimension: 'Code' },
  ]
}

function main() {
  const transportThenPlateau = [
    { round: 1, findings: [], dimensions: allMissingDims() },
    { round: 2, findings: blocking3('r2'), dimensions: allRunDims() },
    { round: 3, findings: blocking3('r3'), dimensions: allRunDims() },
  ]
  const noProgress = checkCircuitBreaker(transportThenPlateau, 7)
  assert.strictEqual(noProgress.halt, false,
    'two real review rounds at 3→3 must not trip no-net-progress when a prior all-missing round exists')

  const threeRealPlateau = [
    { round: 1, findings: blocking3('a'), dimensions: allRunDims() },
    { round: 2, findings: blocking3('b'), dimensions: allRunDims() },
    { round: 3, findings: blocking3('c'), dimensions: allRunDims() },
  ]
  const halt = checkCircuitBreaker(threeRealPlateau, 7)
  assert.strictEqual(halt.halt, true, 'three real review rounds at 3→3→3 must still halt')
  assert.strictEqual(halt.reason, 'no-net-progress')

  console.log('ok: circuit breaker ignores transport-failed rounds for progress checks')
}

main()
