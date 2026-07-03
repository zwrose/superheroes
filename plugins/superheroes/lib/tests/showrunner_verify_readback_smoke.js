// Regression: a long verify command can outlive the courier's default Bash timeout. The verify
// subprocess may still finish and write its durable result, while the courier answers with prose.
// The loop may trust a current round-scoped verify-result read-back, but never stale state or a
// schema-shaped courier invention.
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

const BLOCKER = [{ file: 'a.py', line: 1, title: 'bug', severity: 'Important', evidence: 'x' }]

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

function verifyPath(dir, round) { return path.join(dir, `verify-result-r${round}.json`) }

async function runVerifyCase({ writeCurrentResult = false, staleResult = false, directPass = false } = {}) {
  const dir = freshDir()
  if (staleResult) {
    fs.writeFileSync(verifyPath(dir, 1), JSON.stringify({ result: 'pass', code: 0, tail: 'stale' }))
  }
  let verifyPrompt = ''
  global.reviewerAgent = async (_reviewer, _context, _rubric, runDir, round, opts) => cleanResult(runDir, round, opts)
  global.agent = async (_prompt, opts) => {
    if (opts && opts.label === 'run verify') {
      verifyPrompt = _prompt
      if (writeCurrentResult) {
        fs.writeFileSync(verifyPath(dir, 1), JSON.stringify({ result: 'pass', code: 0, tail: '' }))
      }
      if (directPass) return { result: 'pass', code: 0, tail: '' }
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
    'malformed verify courier answer must certify from current round verify-result pass')
  assert.ok(res.verifyPrompt.includes('--out') && res.verifyPrompt.includes('verify-result-r1.json'),
    'verify courier command writes a round-scoped durable result file')
  assert.ok(res.verifyPrompt.includes('600000 ms'),
    'verify courier prompt names the explicit long Bash timeout')
  assert.ok(res.verifyPrompt.includes('Do NOT background') && res.verifyPrompt.includes('Do NOT answer until'),
    'verify courier prompt forbids backgrounding or early prose answers')

  res = await runVerifyCase({ directPass: true })
  assert.strictEqual(res.verdict.terminal, 'halted',
    'a direct courier {"result":"pass"} without a process-written file must not certify clean')
  assert.match(res.verdict.reason || '', /verify command failed/)

  res = await runVerifyCase()
  assert.strictEqual(res.verdict.terminal, 'halted',
    'malformed verify courier answer with no read-back file still fails closed')
  assert.match(res.verdict.reason || '', /verify command failed/)

  res = await runVerifyCase({ staleResult: true })
  assert.strictEqual(res.verdict.terminal, 'halted',
    'loop-entry sweep must remove stale verify-result.json before a new verify round')
  assert.match(res.verdict.reason || '', /verify command failed/)

  {
    const dir = freshDir()
    let verifyCalls = 0
    global.reviewerAgent = async (_reviewer, _context, _rubric, runDir, round, opts) => {
      if (round === 1) return { findings: BLOCKER, confidence: 'high', verificationReceipt: receipt(runDir, round, opts), usage: { total: 1 } }
      return cleanResult(runDir, round, opts)
    }
    global.agent = async (_prompt, opts) => {
      if (opts && opts.label === 'run verify') {
        verifyCalls += 1
        if (verifyCalls === 1) fs.writeFileSync(verifyPath(dir, 1), JSON.stringify({ result: 'pass', code: 0, tail: '' }))
        return 'The process is running and stdout is redirected to the output file. The command is still executing...'
      }
      return null
    }
    const verdict = await reviewPanel(base(dir))
    assert.strictEqual(verdict.terminal, 'halted',
      'round 2 must not certify from round 1 verify-result after a fix changes the tree')
    assert.match(verdict.reason || '', /verify command failed/)
    assert.ok(verifyCalls >= 2, 'the cross-round case must reach the second verify attempt')
  }

  console.log('ok: verify courier read-back is round-scoped and file-authoritative')
}

main().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
