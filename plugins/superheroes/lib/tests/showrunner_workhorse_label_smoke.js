// plugins/superheroes/lib/tests/showrunner_workhorse_label_smoke.js
const assert = require('assert')
const sr = require('../showrunner.js')
const { implementTaskLabel, fixTaskLabel, reviewTaskLabel } = require('../build_phase.js')

assert.ok(sr.PHASES.includes('workhorse'), 'PHASES must surface the build phase as "workhorse"')
assert.ok(!sr.PHASES.includes('build'), 'the literal "build" phase label must be renamed')

const sample = { id: '3', title: 'Add auth' }
assert.strictEqual(implementTaskLabel(sample, 7), 'implement task 3 of 7')
assert.strictEqual(fixTaskLabel(sample), 'fix task 3')
assert.strictEqual(reviewTaskLabel(sample, 1), 'review task 3:r1')
assert.ok(/^review task .+:r\d+$/.test(reviewTaskLabel(sample, 2)), 'review labels preserve round markers')

console.log('ok: workhorse label')
