require('./_smoke_checkout_root.js')
// Pin cwd to the checkout root: buildPhase's final review runs REAL root-pinned helpers
// (review_setup_gather.py), so repo-relative state only lines up when the smoke itself runs
// from the root (pre-existing; see showrunner_fronthalf_phase_smoke.js for the story).
if (globalThis.__SR_ROOT) process.chdir(globalThis.__SR_ROOT)
const assert = require('assert')
const bp = require('../build_phase.js')
const { routeMatches } = require('./_task_leaf_route.js')

// pid-unique work item: buildPhase's final review derives a machine-global
// /tmp/workhorse-<wi>-final-review dir from the work-item name, so a fixed name shares (and
// reads) state with a concurrent pytest suite on this machine (see _final_review_probe.js for
// the flake story). The dir is reaped on a passing exit; a failing run keeps it as evidence.
const WI = `wi-pid${process.pid}`
process.on('exit', (code) => {
  if (code !== 0) return
  try { require('fs').rmSync(`/tmp/workhorse-${WI}-final-review`, { recursive: true, force: true }) } catch (_) {}
  try { require('fs').rmSync(`/tmp/showrunner-${WI}-review-plan`, { recursive: true, force: true }) } catch (_) {}
})


global.log = () => {}
global.parallel = async (fns) => { for (const f of (fns || [])) await f() }

function makeAgent(routes, labels) {
  return async (prompt, opts) => {
    const label = (opts && opts.label) || ''
    labels.push(label)
    if (label.startsWith('branch-reviewer:')) return { findings: [] }
    for (const [needle, resp] of routes) if (routeMatches(label, needle)) return typeof resp === 'function' ? resp(prompt) : resp
    for (const [needle, resp] of routes) if (prompt.includes(needle)) return typeof resp === 'function' ? resp(prompt) : resp
    if (opts && opts.courier) { for (const [needle, resp] of routes) if (needle === 'exec') return typeof resp === 'function' ? resp(prompt) : resp }
    return ''
  }
}

;(async () => {
  const labels = []
  global.agent = makeAgent([
    ['gather build state', [{ ok: true, stdout: JSON.stringify({
      committed_task_ids: [],
      unmapped_commits: 0,
      review_records: {},
      worktree_dirty: false,
      final_review: null,
      provenance: 'absent',
    }) }]],
    ['exec', (prompt) => {
      if (prompt.includes('read-gate')) return [{ ok: true, stdout: '{"review": "passed"}' }]
      if (prompt.includes('build_entry.py')) return [{ ok: true, stdout: JSON.stringify({ branch: 'superheroes/wi-abc', path: '/tmp/wt' }) }]
      if (prompt.includes('task_list_cli.py')) return [{ ok: true, stdout: JSON.stringify({ tasks: [{ id: '1', title: 'A' }], raw_task_heading_count: 1 }) }]
      if (prompt.includes('fence_cli.py')) return [{ ok: true, stdout: JSON.stringify({ ok: true }) }]
      if (prompt.includes('verify_command_cli.py')) return [{ ok: true, stdout: JSON.stringify({ command: 'none' }) }]
      if (prompt.includes('minor_rollup_cli.py')) return [{ ok: true, stdout: JSON.stringify({ minors: [] }) }]
      if (prompt.includes('record-final-review')) return [{ ok: true, stdout: JSON.stringify({ ok: true, read_back: true }) }]
      if (prompt.includes('prov_entry.py')) return [{ ok: true, stdout: JSON.stringify({ ok: true }) }]
      return [{ ok: true, stdout: '{}' }]
    }],
    ['implement-task', { ok: true, signal: 'ok', evidence: { testFailed: true, testPassed: true } }],
    ['record task built', [{ ok: true, stdout: JSON.stringify({ ok: true, read_back: true, task: '1' }) }]],
    ['task-reviewer:r1', { verdicts: { spec_compliance: 'pass', code_quality: 'pass' }, findings: [] }],
    ['record task reviewed', [{ ok: true, stdout: JSON.stringify({ ok: true, read_back: true, task: '1' }) }]],
    ['read verify + minors', [{ ok: true, stdout: JSON.stringify({ ok: true, verify_command: 'none', minors: [] }) }]],
    ['stamp build coverage', [{ ok: true, stdout: JSON.stringify({ ok: true, read_back: true }) }]],
    ['run verify', { command: 'none', returncode: 0, timedOut: false }],
  ], labels)

  globalThis.reviewerAgent = async () => []
  globalThis.recordDeferred = async () => {}
  const r = await bp.buildPhase(WI, 5)
  assert.strictEqual(r.confidence, 'high')
  assert.deepStrictEqual(
    labels.filter((label) =>
      ['gather build state', 'implement task 1 of 1', 'record task built', 'review task 1:r1', 'record task reviewed'].includes(label)
    ),
    ['gather build state', 'implement task 1 of 1', 'record task built', 'review task 1:r1', 'record task reviewed'],
  )
  assert.ok(!labels.includes('worker'))
  assert.ok(!labels.includes('review'))
  assert.ok(!labels.includes('fixer'))
  console.log('ok: build phase record labels folded')
})().catch((e) => { console.error('FAIL:', e.message || e); process.exit(1) })
