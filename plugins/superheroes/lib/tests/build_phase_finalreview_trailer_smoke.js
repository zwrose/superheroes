// plugins/superheroes/lib/tests/build_phase_finalreview_trailer_smoke.js
// #375 drift guard. Whole-branch final-review fix commits used to carry NO Task-Id (native/default path)
// or the work-item SLUG (external path, via engine_adapter.commit_result(task_id=workItem)) — neither is
// among the numeric task valid_ids, so the spine's OWN fix commits failed the spine's OWN UFR-7 resume
// gate, every time. The fix reserves ONE sentinel identity (`Task-Id: final-review`) that:
//   1. both fix paths mint (native/default via the inline nativeAgentCall prompt; external via the
//      _implDispatch taskId that engine_adapter.commit_result stamps), and
//   2. the build-gather (build_state.py) accepts on its own authority.
// This smoke pins the ONE-SSOT invariant (JS===Python value) + the EXTERNAL-path prompt (fixBranchPrompt).
// The NATIVE/default inline fix prompt's sentinel is covered separately by build_phase_final_review_smoke.js
// (it captures the fired 'fix-branch' prompt and asserts the sentinel), and the external DISPATCH taskId by
// build_phase_engine_smoke.js Scenario 4 — so all three mint sites are guarded across the three smokes.
const assert = require('assert')
const { execFileSync } = require('child_process')
const path = require('path')

const bp = require('../build_phase.js')

// 1. The reserved sentinel is exported and is a NON-numeric, non-empty reserved token (a numeric value
//    would collide with a real task id; an empty value would read as "no trailer").
assert.strictEqual(typeof bp.FINAL_REVIEW_TASK_ID, 'string', 'FINAL_REVIEW_TASK_ID is exported as a string')
assert.ok(bp.FINAL_REVIEW_TASK_ID.length > 0, 'FINAL_REVIEW_TASK_ID is non-empty')
assert.ok(!/^\d+$/.test(bp.FINAL_REVIEW_TASK_ID),
  'FINAL_REVIEW_TASK_ID must NOT be numeric — it must never collide with a real task id')

// 2. SSOT drift guard: the JS constant the fixer mints MUST equal the Python constant the gate accepts.
//    Two languages, one value — pinned here so a change on one side that forgets the other fails in CI,
//    not in a live resume.
const libDir = path.join(__dirname, '..')
const pyValue = execFileSync('python3',
  ['-c', 'import sys; sys.path.insert(0, sys.argv[1]); import build_state; print(build_state.FINAL_REVIEW_TASK_ID)', libDir],
  { encoding: 'utf8' }).trim()
assert.strictEqual(bp.FINAL_REVIEW_TASK_ID, pyValue,
  `JS FINAL_REVIEW_TASK_ID (${bp.FINAL_REVIEW_TASK_ID}) must equal Python build_state.FINAL_REVIEW_TASK_ID (${pyValue})`)

// 3. External-path prompt: fixBranchPrompt (the codex|cursor whole-branch fix prompt) states the sentinel
//    trailer defensively (the external commit is stamped by engine_adapter.commit_result from the taskId).
const fixBranch = bp.fixBranchPrompt('branch-x', '/wt', '[{"title":"blocker"}]')
assert.ok(fixBranch.includes(`Task-Id: ${bp.FINAL_REVIEW_TASK_ID}`),
  'fixBranchPrompt instructs the worker to trailer whole-branch fix commits with the sentinel')
assert.ok(fixBranch.includes('[{"title":"blocker"}]'), 'fixBranchPrompt keeps its findings payload')
assert.ok(fixBranch.includes(bp.workerContractTail()),
  'fixBranchPrompt still carries the shared worker output-contract tail verbatim')

console.log('OK: #375 — final-review fix commits carry the reserved sentinel; JS/Python SSOT pinned; UFR-7 accepts it')
