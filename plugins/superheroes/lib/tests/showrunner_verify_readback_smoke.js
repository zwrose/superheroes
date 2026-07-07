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

async function runVerifyCase({ writeCurrentResult = false, writeNestedCurrentResult = false, staleResult = false, directPass = false, throwWithFile = false, throwNoFile = false } = {}) {
  const dir = freshDir()
  if (staleResult) {
    fs.writeFileSync(verifyPath(dir, 1), JSON.stringify({ result: 'pass', code: 0, tail: 'stale' }))
  }
  let verifyPrompt = ''
  let verifyCalls = 0
  global.reviewerAgent = async (_reviewer, _context, _rubric, runDir, round, opts) => cleanResult(runDir, round, opts)
  global.agent = async (_prompt, opts) => {
    if (opts && opts.label === 'run verify') {
      verifyPrompt = _prompt
      verifyCalls += 1
      if (writeCurrentResult) {
        fs.writeFileSync(verifyPath(dir, 1), JSON.stringify({ result: 'pass', code: 0, tail: '' }))
      }
      if (writeNestedCurrentResult) {
        fs.writeFileSync(verifyPath(dir, 1), JSON.stringify({ result: JSON.stringify({ result: 'pass', code: 0, tail: '' }) }))
      }
      // A verify courier that ran verify_gate.py correctly (durable pass file written) but THREW because
      // it never emitted its StructuredOutput tool call (live wf_1ed21465-6f3, harness-run 26). The throw
      // must be absorbed like an unusable answer so the file-authoritative read-back still arbitrates.
      if (throwWithFile) {
        fs.writeFileSync(verifyPath(dir, 1), JSON.stringify({ result: 'pass', code: 0, tail: '' }))
        throw new Error('verify courier never called its StructuredOutput tool')
      }
      // A thrown courier with NO durable file on either attempt must stay fail-closed.
      if (throwNoFile) throw new Error('verify courier never called its StructuredOutput tool')
      if (directPass) return { result: 'pass', code: 0, tail: '' }
      return 'The process is running and stdout is redirected to the output file. The command is still executing...'
    }
    return null
  }
  const verdict = await reviewPanel(base(dir))
  return { dir, verdict, verifyPrompt, verifyCalls: () => verifyCalls }
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
  assert.ok(res.verifyPrompt.includes('structured output fields must be the JSON object'),
    'verify courier prompt forbids nesting verify_gate JSON as a string result')

  res = await runVerifyCase({ writeNestedCurrentResult: true })
  assert.strictEqual(res.verdict.terminal, 'clean',
    'file-authoritative verify read-back must parse nested {"result":"{\\"result\\":...}"} payloads')

  res = await runVerifyCase({ directPass: true })
  assert.strictEqual(res.verdict.terminal, 'halted',
    'a direct courier {"result":"pass"} without a process-written file must not certify clean')
  assert.match(res.verdict.reason || '', /verify failed/)

  // A THROWN verify courier must be treated exactly like an unusable answer, not collapsed to 'fail'
  // before the file read-back runs (live wf_1ed21465-6f3, harness-run 26). With the round-stamped file
  // saying pass, the round must certify clean from the durable evidence despite the throw.
  res = await runVerifyCase({ throwWithFile: true })
  assert.strictEqual(res.verdict.terminal, 'clean',
    'a thrown verify courier must not bypass the read-back — a round-stamped pass file certifies clean')
  assert.strictEqual(res.verifyCalls(), 1,
    'the file read-back after the thrown courier certifies without a second verify attempt')

  // The companion: a thrown courier that leaves NO durable file (on either attempt) still fails closed.
  res = await runVerifyCase({ throwNoFile: true })
  assert.strictEqual(res.verdict.terminal, 'halted',
    'a thrown verify courier with no read-back file still fails closed')
  assert.match(res.verdict.reason || '', /verify failed/)
  assert.strictEqual(res.verifyCalls(), 4,
    '#279: verifyAgent internal retry (2 courier calls) x the shell bounded corrective re-run (a 2nd verifyAgent on a zero-blocking fail) = 4 before failing closed')

  res = await runVerifyCase()
  assert.strictEqual(res.verdict.terminal, 'halted',
    'malformed verify courier answer with no read-back file still fails closed')
  assert.match(res.verdict.reason || '', /verify failed/)

  res = await runVerifyCase({ staleResult: true })
  assert.strictEqual(res.verdict.terminal, 'halted',
    'loop-entry sweep must remove stale verify-result.json before a new verify round')
  assert.match(res.verdict.reason || '', /verify failed/)

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
    assert.match(verdict.reason || '', /verify failed/)
    assert.ok(verifyCalls >= 2, 'the cross-round case must reach the second verify attempt')
  }

  {
    const dir = freshDir()
    let verifyCalls = 0
    const prompts = []
    global.reviewerAgent = async (_reviewer, _context, _rubric, runDir, round, opts) => cleanResult(runDir, round, opts)
    global.agent = async (_prompt, opts) => {
      if (opts && opts.label === 'run verify') {
        verifyCalls += 1
        prompts.push(_prompt)
        if (verifyCalls === 2) fs.writeFileSync(verifyPath(dir, 1), JSON.stringify({ result: 'pass', code: 0, tail: '' }))
        return 'The command was run, but no structured JSON is available.'
      }
      return null
    }
    const verdict = await reviewPanel(base(dir))
    assert.strictEqual(verdict.terminal, 'clean',
      'one bounded verify courier retry may certify from the same round-stamped read-back file')
    assert.strictEqual(verifyCalls, 2, 'unusable direct answer plus missing read-back gets one retry')
    assert.ok(prompts.every((p) => p.includes('verify-result-r1.json')),
      'verify retry keeps the same round-stamped --out target')
  }

  {
    const dir = freshDir()
    let verifyCalls = 0
    global.reviewerAgent = async (_reviewer, _context, _rubric, runDir, round, opts) => cleanResult(runDir, round, opts)
    global.agent = async (_prompt, opts) => {
      if (opts && opts.label === 'run verify') {
        verifyCalls += 1
        return 'The command was run, but no structured JSON is available.'
      }
      return null
    }
    const verdict = await reviewPanel(base(dir))
    assert.strictEqual(verdict.terminal, 'halted',
      'a second unusable verify courier answer with no read-back file still fails closed')
    assert.match(verdict.reason || '', /verify failed/)
    assert.strictEqual(verifyCalls, 4,
      '#279: verify read-back recovery (2 courier calls) x the shell bounded corrective re-run (2) = 4 on a zero-blocking fail')
  }

  console.log('ok: verify courier read-back is round-scoped and file-authoritative')
}

main().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
