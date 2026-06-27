// Smoke: panel_tally.resume_round reconstructs the round boundary from disk (UFR-7/8).
// Run: node plugins/superheroes/lib/tests/showrunner_resume_smoke.js
const { execFileSync } = require('child_process')
const assert = require('assert')
const fs = require('fs')
const os = require('os')
const path = require('path')
const sr = require('../showrunner.js')

const run = fs.mkdtempSync(path.join(os.tmpdir(), 'resume-smoke-'))
const tally = 'plugins/superheroes/lib/panel_tally.py'

function py(args) {
  return execFileSync('python3', args, { encoding: 'utf8' })
}

// Round 1 fully saved (writes round-1/verdict.json), round 2 only partial (dir, no verdict).
fs.mkdirSync(path.join(run, 'round-1'), { recursive: true })
fs.writeFileSync(path.join(run, 'round-1', 'findings-code.json'), '[]')
py([tally, '--run-dir', run, '--round', '1', '--roster', 'code', '--max-rounds', '7'])
fs.mkdirSync(path.join(run, 'round-2'), { recursive: true })  // partial: no verdict.json

const out = py(['-c',
  `import sys; sys.path.insert(0,'plugins/superheroes/lib'); import panel_tally; ` +
  `print(panel_tally.resume_round(${JSON.stringify(run)}))`]).trim()

if (out !== '2') {
  console.error(`FAIL: resume_round expected 2, got ${out}`)
  process.exit(1)
}

let checkpointPrompt = ''
global.parallel = async (thunks) => Promise.all(thunks.map((t) => t()))
global.log = () => {}
global.agent = async (prompt) => {
  if (prompt.includes('checkpoint_entry')) checkpointPrompt = prompt
  return { ok: true, pr: null }
}

sr.recordCursor('wi', 3, 'review-tasks', { ready: true }).then(() => {
  assert.ok(checkpointPrompt.includes("--step '3'"), 'recordCursor passes the numeric cursor')
  assert.ok(checkpointPrompt.includes("--phase 'review-tasks'"), 'recordCursor passes the phase cursor')
  assert.ok(checkpointPrompt.includes('--json'), 'recordCursor preserves side-effect writes')
  console.log('ok: resume_round skips the partial round and recordCursor writes step+phase')
}).catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
