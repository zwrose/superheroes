// plugins/superheroes/lib/tests/build_phase_fix_contract_smoke.js
// #357 WORKER OUTPUT-CONTRACT drift guard. The 2026-07-10 acceptance runs proved the class: the
// external FIX dispatch prompts ended at the findings array with NO output contract, while
// engine_adapter.parse_result's build|fix branch REQUIRES the {"ok":…} verdict object — so every
// external fix leaf did the work, ended with prose, and parsed `unreadable` (the configured fix
// engine could never genuinely land its work; build leaves, whose prompt states the contract,
// complied 2/2 the same day). This smoke pins: every external write-role worker prompt carries the
// ONE shared contract tail, and that tail names exactly the fields the parser consumes.
const assert = require('assert')

const bp = require('../build_phase.js')

const tail = bp.workerContractTail()

// The tail demands the verdict shape parse_result consumes (engine_adapter.py build|fix branch):
// strict `ok`, the two recognized signals, both evidence booleans, and the deniedAction honesty field.
assert.ok(tail.includes('Return JSON'), 'the contract tail demands a JSON verdict')
for (const needle of ['"ok":bool', 'needs_context', 'plan_wrong', '"testFailed":bool',
  '"testPassed":bool', '"deniedAction"', 'never fabricate']) {
  assert.ok(tail.includes(needle), `the contract tail carries ${JSON.stringify(needle)}`)
}

// Every external write-role worker prompt carries the SAME tail — build, task-level fix, and
// whole-branch fix. A new dispatch site composed without the tail should fail here, not in a live run.
const task = { id: 3, title: 'do the thing' }
const built = bp.buildTaskPrompt(task, 'branch-x', '/wt', '/docs/tasks.md', '', '')
const fixTask = bp.fixTaskPrompt(task, 'branch-x', '/wt', '[{"severity":"Important"}]')
const fixBranch = bp.fixBranchPrompt('branch-x', '/wt', '[{"title":"blocker"}]')
for (const [name, prompt] of [['buildTaskPrompt', built], ['fixTaskPrompt', fixTask],
  ['fixBranchPrompt', fixBranch]]) {
  assert.ok(prompt.includes(tail), `${name} carries the shared worker output-contract tail verbatim`)
}

// The fix prompts still carry their own load-bearing parts alongside the tail.
assert.ok(fixTask.includes('Task-Id: 3') && fixTask.includes('[{"severity":"Important"}]'),
  'fixTaskPrompt keeps the trailer instruction and the findings payload')
assert.ok(fixBranch.includes('whole-branch blocking findings') && fixBranch.includes('[{"title":"blocker"}]'),
  'fixBranchPrompt keeps its findings payload')

console.log('OK: worker output contract — one shared tail, present on build + both external fix prompts, matching the parser')
