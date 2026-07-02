// Smoke: the shared review-and-fix loop never ships an unbounded record body through the
// courier pipe (live 2026-07-02: the haiku courier mangled the oversized inline --record-json,
// persistRoundRecord failed, and every native review leg parked cannot-certify:
// round-memory-write-failed; the telemetry + terminal-record writes failed the same way).
// Asserts, on a round with realistically LARGE findings:
//   (a) every review_memory/review_telemetry helper invocation carries only paths + small
//       scalars — no --record-json/--payload-json, no arg anywhere near the record size;
//   (b) the round record still lands complete on disk (composed Python-side from the staged
//       per-dimension files), and the verdict's telemetry is the small summary (no rounds);
//   (c) fencedJsonWrite stages its payload as a file (--payload-path), never inline.
'use strict'
const assert = require('assert')
const fs = require('fs'); const os = require('os'); const path = require('path')
const { reviewPanel } = require('../review_panel_shell.js')
const { fencedJsonWrite } = require('../fenced_json.js')
const { defaultIo } = require('../io_seam.js')

globalThis.parallel = async (thunks) => Promise.all(thunks.map((t) => t()))
globalThis.log = () => {}
globalThis.synthesisLeaf = async () => ({ verdicts: [], usage: { total: 1 } })
globalThis.recordDeferred = async () => {}
globalThis.agent = async () => null

const BIG_EVIDENCE = 'x'.repeat(2048)
const BIG_FINDINGS = Array.from({ length: 60 }, (_, i) => ({
  file: 'a.py', line: i + 1, title: `finding ${i}`, severity: 'Critical',
  taxonomy: 'bug', evidence: BIG_EVIDENCE,
}))
const RECORD_SIZE = JSON.stringify(BIG_FINDINGS).length   // ~130KB
const ARG_BOUND = 8192   // helper args must stay paths + small scalars

function receipt(runId, round) {
  return { artifact: `${runId}:round-${round}`, chain: [
    { step: 'citation', evidence: 'reviewed citations' }, { step: 'reachability', evidence: 'validated call path' },
    { step: 'missing-check', evidence: 'checked missing FRs' }, { step: 'tooling', evidence: 'smoke passed' }],
    coverageDecisionIds: [] }
}

// Wrap the disk io: real behavior, but capture every runHelper invocation's args + stdout size.
const helperCalls = []
const helperResults = []
globalThis.io = Object.assign({}, defaultIo, {
  async runHelper(cmd, args) {
    helperCalls.push([cmd].concat(args || []))
    const out = await defaultIo.runHelper(cmd, args)
    helperResults.push({ args: args || [], stdout: out.stdout || '' })
    return out
  },
})

async function main() {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'loop-payload-'))
  let round = 0
  globalThis.reviewerAgent = async (_r, _c, _rub, runDir, r) => {
    round += 1
    return round === 1
      ? { findings: BIG_FINDINGS, confidence: 'high', verificationReceipt: receipt(runDir, r), usage: { total: 1 } }
      : { findings: [], confidence: 'high', verificationReceipt: receipt(runDir, r), usage: { total: 1 } }
  }
  const v = await reviewPanel({
    reviewerSet: ['code'], context: {}, rubric: 'r', runKey: dir, runDir: dir,
    fixStep: async () => ({ fixed: BIG_FINDINGS.map((f) => `${f.file}::${f.title}`), changedSubjects: ['Code'], coverageDecisions: [] }),
    maxRounds: 7, legKind: { panel: true, code: false },
  })
  assert.strictEqual(v.terminal, 'clean', `large-findings loop must still converge clean, got ${v.terminal} (${v.reason})`)

  // (a) no unbounded inline body in ANY loop helper invocation
  for (const call of helperCalls) {
    const script = String(call[1] || '')
    if (!/review_memory|review_telemetry|fenced_json/.test(script)) continue
    assert.ok(!call.includes('--record-json'), `--record-json still present: ${script}`)
    assert.ok(!call.includes('--payload-json'), `--payload-json still present: ${script}`)
    for (const arg of call) {
      assert.ok(String(arg).length <= ARG_BOUND,
        `helper arg of ${String(arg).length}B (record is ${RECORD_SIZE}B) rides the courier inline: ${script} ${String(arg).slice(0, 80)}…`)
    }
  }

  // (b) the record landed complete on disk, composed from the staged per-dimension files
  const recs = JSON.parse(fs.readFileSync(path.join(dir, 'round-records.json'), 'utf8'))
  const r1 = recs.find((r) => r.round === 1)
  assert.ok(r1, 'round 1 record persisted')
  assert.strictEqual(r1.findings.length, BIG_FINDINGS.length, 'all large findings persisted')
  assert.strictEqual(r1.findings[0].evidence, BIG_EVIDENCE, 'finding bodies intact')
  assert.deepStrictEqual(r1.fix && r1.fix.fixes.length, BIG_FINDINGS.length, 'post-fix delta applied')
  assert.ok(fs.existsSync(path.join(dir, 'dim-result-code-r1.json')), 'per-dimension result staged as a file')
  // telemetry attached to the verdict is the SMALL summary — rounds stay on disk only
  assert.ok(v.telemetry && v.telemetry.benchmarkValid !== undefined, 'verdict carries telemetry summary')
  assert.ok(!('rounds' in v.telemetry), 'verdict.telemetry must NOT embed the rounds')
  const telem = JSON.parse(fs.readFileSync(path.join(dir, 'review-telemetry.json'), 'utf8'))
  assert.ok(Array.isArray(telem.rounds) && telem.rounds.length >= 1, 'on-disk telemetry keeps full rounds')

  // (c) fencedJsonWrite stages the payload as a verified file, never inline
  helperCalls.length = 0
  const recPath = path.join(dir, 'terminal-record.json')
  const bigVerdict = { schemaVersion: 1, terminal: 'clean', findings: BIG_FINDINGS }
  const w = await fencedJsonWrite(recPath, bigVerdict, { expectedHash: defaultIo.contentHash(''), runId: 'run-x' })
  assert.strictEqual(w.ok, true, `fencedJsonWrite failed: ${JSON.stringify(w)}`)
  const written = JSON.parse(fs.readFileSync(recPath, 'utf8'))
  assert.strictEqual(written.findings.length, BIG_FINDINGS.length)
  const fjCall = helperCalls.find((c) => String(c[1]).includes('fenced_json.py'))
  assert.ok(fjCall, 'fencedJsonWrite went through the helper')
  assert.ok(fjCall.includes('--payload-path'), 'fencedJsonWrite must pass --payload-path')
  assert.ok(!fjCall.includes('--payload-json'), 'fencedJsonWrite must not pass --payload-json')
  for (const arg of fjCall) assert.ok(String(arg).length <= ARG_BOUND, 'fenced write arg too large')
  assert.ok(!fs.existsSync(recPath + '.payload'), 'staged payload file consumed on success')

  // (d) the RESUME read is bounded too: a large on-disk history loads as summaries via
  // load-summary — the evidence bodies never ride the courier stdout back (the read twin
  // of the compose-persist fix).
  const rdir = fs.mkdtempSync(path.join(os.tmpdir(), 'loop-resume-'))
  const bigRecs = [1, 2].map((rnd) => ({
    schemaVersion: 2, round: rnd, kind: 'baseline', confirmationPending: false,
    changedSubjects: ['Code'], coverageDecisions: [], tokenUsage: {},
    findings: BIG_FINDINGS, carriedFindings: [],
    dimensions: { code: { dimension: 'code', status: 'run', confidence: 'high', round: rnd, findings: BIG_FINDINGS, subjects: ['Code'] } },
  }))
  fs.writeFileSync(`${rdir}/round-records.json`, JSON.stringify(bigRecs))
  const onDisk = fs.statSync(`${rdir}/round-records.json`).size
  helperResults.length = 0
  globalThis.reviewerAgent = async (_r, _c, _rub, runDir, r) =>
    ({ findings: [], confidence: 'high', verificationReceipt: receipt(runDir, r), usage: { total: 1 } })
  const rv = await reviewPanel({
    reviewerSet: ['code'], context: {}, rubric: 'r', runKey: rdir, runDir: rdir,
    fixStep: async () => ({ fixed: [], changedSubjects: ['Code'], coverageDecisions: [] }),
    maxRounds: 7, legKind: { panel: true, code: false },
  })
  assert.ok(rv && typeof rv.terminal === 'string', 'resume run reaches a terminal')
  const loadCall = helperResults.find((h) => h.args.includes('load-summary'))
  assert.ok(loadCall, 'the resume seed goes through load-summary')
  assert.ok(loadCall.stdout.length < onDisk / 5,
    `resume load stdout must be bounded (${loadCall.stdout.length}B vs ${onDisk}B on disk)`)
  assert.ok(!loadCall.stdout.includes(BIG_EVIDENCE), 'evidence bodies never ride the load stdout')
  const plainLoad = helperResults.find((h) => h.args.includes('load') && !h.args.includes('load-summary'))
  assert.ok(!plainLoad, 'the full-echo load verb must not be used by the loop')

  console.log('ok: review-loop persistence ships paths + small scalars only (no mega-JSON through the courier)')
}

main().catch((e) => { console.error('FAIL:', e.message || e); process.exit(1) })
