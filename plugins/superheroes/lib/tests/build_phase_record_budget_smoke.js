const assert = require('assert')
const bp = require('../build_phase.js')

global.log = () => {}
global.parallel = async (fns) => { for (const f of (fns || [])) await f() }

function makeAgent(routes, labels) {
  return async (prompt, opts) => {
    const label = (opts && opts.label) || ''
    labels.push(label)
    for (const [needle, resp] of routes) if (label === needle) return typeof resp === 'function' ? resp(prompt) : resp
    for (const [needle, resp] of routes) if (prompt.includes(needle)) return typeof resp === 'function' ? resp(prompt) : resp
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
      if (prompt.includes('read-gate')) return [{ index: 0, ok: true, stdout: 'passed' }]
      if (prompt.includes('build_entry.py')) return [{ index: 0, ok: true, stdout: JSON.stringify({ branch: 'superheroes/wi-abc', path: '/tmp/wt' }) }]
      if (prompt.includes('task_list_cli.py')) return [{ index: 0, ok: true, stdout: JSON.stringify({ tasks: [{ id: '1', title: 'A' }], raw_task_heading_count: 1 }) }]
      if (prompt.includes('fence_cli.py')) return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
      if (prompt.includes('verify_command_cli.py')) return [{ index: 0, ok: true, stdout: JSON.stringify({ command: 'none' }) }]
      if (prompt.includes('minor_rollup_cli.py')) return [{ index: 0, ok: true, stdout: JSON.stringify({ minors: [] }) }]
      if (prompt.includes('record-final-review')) return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
      if (prompt.includes('prov_entry.py')) return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
      return [{ index: 0, ok: true, stdout: '{}' }]
    }],
    ['implement-task', { ok: true, signal: 'ok', evidence: { testFailed: true, testPassed: true } }],
    ['record task built', [{ ok: true, stdout: JSON.stringify({ ok: true, read_back: true, task: '1' }) }]],
    ['task-reviewer:r1', { verdicts: { spec_compliance: 'pass', code_quality: 'pass' }, findings: [] }],
    ['record task reviewed', [{ ok: true, stdout: JSON.stringify({ ok: true, read_back: true, task: '1' }) }]],
    ['reviewer:1', { findings: [] }],
    ['verify_gate.py', { command: 'none', returncode: 0, timedOut: false }],
  ], labels)

  globalThis.reviewerAgent = async () => []
  globalThis.recordDeferred = async () => {}
  const r = await bp.buildPhase('wi', 5)
  assert.strictEqual(r.confidence, 'high')
  assert.deepStrictEqual(
    labels.filter((label) =>
      ['gather build state', 'implement-task', 'record task built', 'task-reviewer:r1', 'record task reviewed'].includes(label)
    ),
    ['gather build state', 'implement-task', 'record task built', 'task-reviewer:r1', 'record task reviewed'],
  )
  assert.ok(!labels.includes('worker'))
  assert.ok(!labels.includes('review'))
  assert.ok(!labels.includes('fixer'))
  console.log('ok: build phase record labels folded')
})().catch((e) => { console.error('FAIL:', e.message || e); process.exit(1) })
