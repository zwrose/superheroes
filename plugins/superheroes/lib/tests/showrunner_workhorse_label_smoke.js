// plugins/superheroes/lib/tests/showrunner_workhorse_label_smoke.js
const assert = require('assert')
const sr = require('../showrunner.js')
assert.ok(sr.PHASES.includes('workhorse'), 'PHASES must surface the build phase as "workhorse"')
assert.ok(!sr.PHASES.includes('build'), 'the literal "build" phase label must be renamed')
console.log('ok: workhorse label')
