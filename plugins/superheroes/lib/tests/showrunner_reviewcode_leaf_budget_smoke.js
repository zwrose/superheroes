const assert = require('assert')
const fs = require('fs')
const os = require('os')
const path = require('path')
const sr = require('../showrunner.js')

global.log = () => {}
global.parallel = async (fns) => { const out = []; for (const f of (fns || [])) out.push(await f()); return out }

;(async () => {
  const labels = []
  let reviewerCalls = 0
  global.agent = async (prompt, opts) => {
    const label = (opts && opts.label) || ''
    labels.push(label)
    if (label === 'resolve review target') {
      // #118 entry fold: the ONE gather carries worktree + head + config + cwd head
      return [{ ok: true, stdout: JSON.stringify({ ok: true, worktree: '/tmp/wt', expectedHead: 'abc123', config: { verifyCommand: 'none', tiers: {} }, cwdHead: 'cwd000' }) }]
    }
    if (label === 'exec' && prompt.includes('review_code_config.py')) {
      throw new Error('config must ride the resolve review target gather, not its own leaf (#118 entry fold)')
    }
    if (label === 'exec' && prompt.includes('git -C') && prompt.includes('rev-parse')) return 'abc123'
    if (label === 'exec' && prompt.includes('git rev-parse')) return 'cwd000'
    if (/^(architecture|code|security|test|premortem)-reviewer:r/.test(label)) {
      reviewerCalls += 1
      return { findings: reviewerCalls === 1 ? [{ id: 'X', file: 'a.js', title: 'bug', severity: 'Important' }] : [] }
    }
    if (label.startsWith('fix-code')) return { fixed: ['X'], deferred: [], changedSubjects: ['Code'], coverageDecisions: [] }
    if (label === 'run verify') return { command: 'none', returncode: 0, timedOut: false }
    if (label === 'stamp review coverage') {
      return [{ ok: true, stdout: JSON.stringify({ ok: true }) }]
    }
    if (label.startsWith('synthesis:')) return { verdicts: [] }
    return [{ index: 0, ok: true, stdout: JSON.stringify({ ok: true }) }]
  }

  // fresh runDir per run: the default derived dir persists round-records.json across runs (stale-state trap)
  const out = await sr.reviewCodePhase('wi', { runDir: fs.mkdtempSync(path.join(os.tmpdir(), 'rc-budget-')) })
  assert.strictEqual(out.gate, 'passed')
  assert.ok(labels.includes('resolve review target'))
  assert.ok(labels.includes('run verify'))
  assert.ok(labels.some((l) => /^(architecture|code|security|test|premortem)-reviewer:r1$/.test(l)))
  assert.ok(labels.includes('stamp review coverage'))
  assert.ok(labels.filter((l) => l === 'run verify').length >= 1)
  console.log('ok: review-code leaf budget folds')
})().catch((e) => { console.error('FAIL:', e.message || e); process.exit(1) })
