// plugins/superheroes/lib/tests/test_eval_clamp.js
//
// Standalone Node.js test for eval_clamp.js. Run via: node <this file> from repo root,
// or via the `test_eval_clamp_runs` pytest test in test_showrunner_node_smokes.py.
// NOT added to SHOWRUNNER_SMOKES — see the enforcement-guard note in the plan.
const assert = require('assert');
const path = require('path');
const { clamp } = require(path.join(__dirname, '..', 'eval_clamp.js'));

// FR-1: in-range
assert.strictEqual(clamp(5, 0, 10), 5, 'in-range: should return value');

// FR-1: below-range
assert.strictEqual(clamp(-3, 0, 10), 0, 'below-range: should return lo');

// FR-1: above-range
assert.strictEqual(clamp(42, 0, 10), 10, 'above-range: should return hi');

// FR-1: inclusive lower bound
assert.strictEqual(clamp(0, 0, 10), 0, 'inclusive lower bound: should return lo');

// FR-1: inclusive upper bound
assert.strictEqual(clamp(10, 0, 10), 10, 'inclusive upper bound: should return hi');

// UP-1: inverted range (lo > hi) — deterministically returns hi = 0
assert.strictEqual(clamp(5, 10, 0), 0, 'inverted range: should return hi');

// FR-2: purity — same call twice yields same result
assert.strictEqual(clamp(7, 2, 9), clamp(7, 2, 9), 'pure: same args yield same result');

console.log('test_eval_clamp.js: all assertions passed');
