// Smoke: frontHalfBoundary composes the run-outcome envelope — in-process via
// frontHalfTwin.renderRunOutcome (Task 18 rewire). Stubs io() + the loop_readout exec leaves.
// Assertions:
//   (a) returns { outcome:'parked', phase:'front-half-boundary' }
//   (b) the envelope header appears in the reason (in-process twin was called)
//   (c) NO agent call for 'render-outcome' (that agent is eliminated by Task 18)
//   (d) loop_readout.py exec is issued per phase_record (the exec leaf is preserved)
const assert = require('assert')
const sr = require('../showrunner.js')
global.parallel = async (thunks) => Promise.all(thunks.map((t) => t()))
global.log = () => {}

const agentCalls = []
global.agent = async (prompt, opts) => {
  agentCalls.push({ prompt: String(prompt), label: (opts && opts.label) || '' })
  // Stub loop_readout exec leaves — return a known sentinel
  if (typeof prompt === 'string' && prompt.includes('loop_readout.py')) {
    return '## stub readout\n\n- terminal: clean\n'
  }
  return null
}

async function main() {
  agentCalls.length = 0
  const r = await sr.frontHalfBoundary('wi')
  assert.strictEqual(r.outcome, 'parked', 'the boundary parks')
  assert.strictEqual(r.phase, 'front-half-boundary', 'names the front-half boundary')
  // (b) envelope header is in the reason — produced in-process by the twin
  assert.ok(/Front-half run outcome/.test(r.reason), 'envelope header in reason (in-process twin ran)')
  // (c) NO agent call for render-outcome (that agent is eliminated in Task 18)
  const renderOutcomeCall = agentCalls.find((c) => c.prompt.includes('render-outcome'))
  assert.ok(!renderOutcomeCall, 'render-outcome agent must NOT be called after Task 18 rewire')
  // (d) loop_readout.py exec is issued (per-phase readout exec leaf is preserved)
  const readoutCall = agentCalls.find((c) => c.prompt.includes('loop_readout.py'))
  assert.ok(readoutCall, 'loop_readout.py exec must still be called (render executor preserved)')

  // (e) FIX 5 (#115 final review, test-002): when the durable outcome write THROWS (recordOk=false),
  // frontHalfBoundary must surface the UFR-6 fallback reason AND skip the loop_readout exec entirely
  // (no readout seam without a successful record write). A mutant that ignores the write error
  // (keeps recordOk=true) would still emit the envelope + call loop_readout — and FAIL here.
  agentCalls.length = 0
  // Stub the io seam so the fenced write cannot stage its payload: stageAndRunHelper (the fold-1
  // stage+verify op, #141) fails, so fencedJsonWrite exhausts its retry and returns not-ok.
  // readJson returns the caller's default (no notify/records).
  global.io = {
    async writeFile() { throw new Error('disk full') },
    async stageAndRunHelper() { return { ok: false, status: 1, stdout: '', stderr: 'stage write failed' } },
    async readText() { return '' },
    async readJson(_p, dflt) { return dflt },
    async mkdirp() {},
    tmpdir() { return '/tmp' },
    join() { return Array.prototype.slice.call(arguments).join('/') },
    contentHash(text) { return require('crypto').createHash('sha256').update(String(text || ''), 'utf8').digest('hex') },
    async runHelper() { return { ok: false, status: 1, stdout: '', stderr: 'unreachable: stage write failed' } },
  }
  try {
    const rf = await sr.frontHalfBoundary('wi-writefail')
    assert.strictEqual(rf.outcome, 'parked', 'write-fail boundary still parks')
    assert.ok(/UFR-6/.test(rf.reason),
      'FIX 5: a failed durable readout write surfaces the UFR-6 fallback reason')
    assert.ok(/could not be written|treat the durable readout as missing/i.test(rf.reason),
      'FIX 5: the fallback reason names the missing durable readout')
    const readoutAfterFail = agentCalls.find((c) => c.prompt.includes('loop_readout.py'))
    assert.ok(!readoutAfterFail,
      'FIX 5: loop_readout exec is NOT called when the record write failed (recordOk=false)')
  } finally {
    delete global.io
  }
  console.log('ok: frontHalfBoundary — in-process twin (no render-outcome agent) + loop_readout exec + UFR-6 write-fail fallback (FIX5)')
}
main().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
