// Regression: a long verify command can outlive the courier's default Bash timeout. The verify
// subprocess may still finish and write its durable result, while the courier answers with prose.
// The loop may trust a current verify-result.json read-back, but never a stale one from loop entry.
const assert = require('assert')
const fs = require('fs'); const os = require('os'); const path = require('path')
const { reviewPanel } = require('../review_panel_shell.js')

global.parallel = async (thunks) => Promise.all(thunks.map((t) => t()))
global.log = () => {}
global.synthesisLeaf = async () => ({ verdicts: [], usage: { total: 1 } })
global.recordDeferred = async () => {}

function freshDir() { return fs.mkdtempSync(path.join(os.tmpdir(), 'verify-readback-')) }

function receipt(runId, round, opts = {}) {
  return {
    artifact: `${runId}:round-${round}`,
    chain: [
      { step: 'citation', evidence: 'reviewed citations' },
      { step: 'reachability', evidence: 'validated call path' },
      { step: 'missing-check', evidence: 'checked missing FRs' },
      { step: 'tooling', evidence: 'smoke passed' },
    ],
    coverageDecisionIds: ((opts.coverageDecisions || []).map((d) => d.id).filter(Boolean)),
  }
}

function cleanResult(runDir, round, opts = {}) {
  return { findings: [], confidence: 'high', verificationReceipt: receipt(runDir, round, opts), usage: { total: 1 } }
}

function base(dir) {
  return {
    reviewerSet: ['code-reviewer'],
    context: {},
    rubric: 'review-base',
    runKey: dir,
    runDir: dir,
    fixStep: async () => ({ changedSubjects: ['Code'], coverageDecisions: [] }),
    maxRounds: 7,
    legKind: { panel: true, code: true },
    verifyCommand: 'python3 -m pytest very-slow-suite -q',
  }
}

async function runVerifyCase({ writeCurrentResult = false, staleResult = false } = {}) {
  const dir = freshDir()
  if (staleResult) {
    fs.writeFileSync(path.join(dir, 'verify-result.json'), JSON.stringify({ result: 'pass', code: 0, tail: 'stale' }))
  }
  let verifyPrompt = ''
  global.reviewerAgent = async (_reviewer, _context, _rubric, runDir, round, opts) => cleanResult(runDir, round, opts)
  global.agent = async (_prompt, opts) => {
    if (opts && opts.label === 'run verify') {
      verifyPrompt = _prompt
      if (writeCurrentResult) {
        fs.writeFileSync(path.join(dir, 'verify-result.json'), JSON.stringify({ result: 'pass', code: 0, tail: '' }))
      }
      return 'The process is running and stdout is redirected to the output file. The command is still executing...'
    }
    return null
  }
  const verdict = await reviewPanel(base(dir))
  return { dir, verdict, verifyPrompt }
}

async function main() {
  let res = await runVerifyCase({ writeCurrentResult: true })
  assert.strictEqual(res.verdict.terminal, 'clean',
    'malformed verify courier answer must certify from current verify-result.json pass')
  assert.ok(res.verifyPrompt.includes('--out') && res.verifyPrompt.includes('verify-result.json'),
    'verify courier command writes a durable result file')
  assert.ok(res.verifyPrompt.includes('600000 ms'),
    'verify courier prompt names the explicit long Bash timeout')
  assert.ok(res.verifyPrompt.includes('Do NOT background') && res.verifyPrompt.includes('Do NOT answer until'),
    'verify courier prompt forbids backgrounding or early prose answers')

  res = await runVerifyCase()
  assert.strictEqual(res.verdict.terminal, 'halted',
    'malformed verify courier answer with no read-back file still fails closed')
  assert.match(res.verdict.reason || '', /verify command failed/)

  res = await runVerifyCase({ staleResult: true })
  assert.strictEqual(res.verdict.terminal, 'halted',
    'loop-entry sweep must remove stale verify-result.json before a new verify round')
  assert.match(res.verdict.reason || '', /verify command failed/)

  console.log('ok: verify courier prose falls back to current read-back only')
}

main().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
