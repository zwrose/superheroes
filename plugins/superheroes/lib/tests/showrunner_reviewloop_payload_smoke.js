// Smoke: the shared review-and-fix loop never ships an unbounded record body through the
// courier pipe (live 2026-07-02: the haiku courier mangled the oversized inline --record-json,
// persistRoundRecord failed, and every native review leg parked cannot-certify:
// round-memory-write-failed; the telemetry + terminal-record writes failed the same way).
// Asserts, on a round with realistically LARGE findings, the D3 durability contract:
//   (a) every review_memory/review_telemetry helper invocation stays bounded — the ONE inline
//       record arg is the self-verified SKELETON (--record-hash = sha256(--record-json), no
//       evidence bodies, small), never the full record;
//   (b) round-records.json lands as skeletons (identity/severity survive; bodies never touch
//       it); the dropped/deferred bodies land in the best-effort round-bodies dump; the
//       verdict's telemetry is the small summary and the on-disk telemetry embeds no rounds;
//   (c) fencedJsonWrite stages its payload as a file (--payload-path + --payload-hash),
//       never inline.
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

// Wrap the disk io: real behavior, but capture every helper invocation's args + stdout size. The
// stageAndRunHelper fold (fold 1, #141) routes the fenced write's stage+verify through ONE op, so
// it is captured the same way as runHelper (its (cmd,args) appended to helperCalls).
const helperCalls = []
const helperResults = []
const stageRuns = []
globalThis.io = Object.assign({}, defaultIo, {
  async runHelper(cmd, args) {
    helperCalls.push([cmd].concat(args || []))
    const out = await defaultIo.runHelper(cmd, args)
    helperResults.push({ args: args || [], stdout: out.stdout || '' })
    return out
  },
  async stageAndRunHelper(stagedPath, text, cmd, args) {
    stageRuns.push({ stagedPath, textLen: String(text).length })
    helperCalls.push([cmd].concat(args || []))
    const out = await defaultIo.stageAndRunHelper(stagedPath, text, cmd, args)
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
    fixStep: async () => ({
      fixed: BIG_FINDINGS.slice(1).map((f) => `${f.file}::${f.title}`),
      deferred: [{ identity: `${BIG_FINDINGS[0].file}::${BIG_FINDINGS[0].title}`, severity: 'Critical', reason: 'out of scope for this branch', finding: BIG_FINDINGS[0] }],
      changedSubjects: ['Code'], coverageDecisions: [],
    }),
    maxRounds: 7, legKind: { panel: true, code: false },
  })
  assert.strictEqual(v.terminal, 'clean', `large-findings loop must still converge clean, got ${v.terminal} (${v.reason})`)

  // (a) every loop helper invocation stays bounded; the one inline record is the self-verified
  // skeleton (record-hash = sha256 of record-json, no evidence bodies)
  for (const call of helperCalls) {
    const script = String(call[1] || '')
    if (!/review_memory|review_telemetry|fenced_json/.test(script)) continue
    assert.ok(!call.includes('--payload-json'), `--payload-json still present: ${script}`)
    for (const arg of call) {
      assert.ok(String(arg).length <= ARG_BOUND,
        `helper arg of ${String(arg).length}B (record is ${RECORD_SIZE}B) rides the courier inline: ${script} ${String(arg).slice(0, 80)}…`)
    }
    const rjIdx = call.indexOf('--record-json')
    if (rjIdx >= 0) {
      const recordJson = String(call[rjIdx + 1])
      assert.ok(!recordJson.includes(BIG_EVIDENCE), 'the inline record must be the skeleton (no evidence bodies)')
      assert.strictEqual(call[call.indexOf('--record-hash') + 1], defaultIo.contentHash(recordJson),
        'the inline record must self-verify (--record-hash = sha256 of --record-json)')
    }
  }

  // (b) D3: round-records.json holds SKELETONS — identity/severity survive, bodies never land
  const recsText = fs.readFileSync(path.join(dir, 'round-records.json'), 'utf8')
  assert.ok(!recsText.includes(BIG_EVIDENCE), 'finding bodies must never land in round-records.json')
  const recs = JSON.parse(recsText)
  const r1 = recs.find((r) => r.round === 1)
  assert.ok(r1, 'round 1 record persisted')
  assert.strictEqual(r1.findings.length, BIG_FINDINGS.length, 'every finding skeleton persisted')
  assert.strictEqual(r1.findings[0].severity, 'Critical', 'skeletons keep identity/severity')
  assert.deepStrictEqual(r1.fix && r1.fix.fixes.length, BIG_FINDINGS.length - 1, 'post-fix delta applied')
  assert.ok(!fs.existsSync(path.join(dir, 'dim-result-code-r1.json')),
    'the per-dimension staging ceremony is gone (D3: one skeleton leaf)')
  // the deferred finding's FULL body rides the best-effort round-bodies dump (the audit target)
  const bodies = JSON.parse(fs.readFileSync(path.join(dir, 'round-bodies-r1.json'), 'utf8'))
  assert.strictEqual(bodies.round, 1)
  assert.strictEqual(bodies.deferred[0].finding.evidence, BIG_EVIDENCE, 'deferred bodies dumped in full')
  // telemetry attached to the verdict is the SMALL summary — and the on-disk record matches
  assert.ok(v.telemetry && v.telemetry.benchmarkValid !== undefined, 'verdict carries telemetry summary')
  assert.ok(!('rounds' in v.telemetry), 'verdict.telemetry must NOT embed the rounds')
  const telem = JSON.parse(fs.readFileSync(path.join(dir, 'review-telemetry.json'), 'utf8'))
  assert.ok(!('rounds' in telem), 'D3: on-disk telemetry must not duplicate the round records')
  assert.ok(telem.roundCount >= 1, 'telemetry keeps the round scalars')

  // (c) fencedJsonWrite stages the payload as a verified file, never inline — and stage+verify
  // ride ONE leaf (fold 1, #141): exactly one stageAndRunHelper op, no separate writeFile leaf.
  helperCalls.length = 0
  stageRuns.length = 0
  const recPath = path.join(dir, 'terminal-record.json')
  const bigVerdict = { schemaVersion: 1, terminal: 'clean', findings: BIG_FINDINGS }
  const w = await fencedJsonWrite(recPath, bigVerdict, { expectedHash: defaultIo.contentHash(''), runId: 'run-x' })
  assert.strictEqual(w.ok, true, `fencedJsonWrite failed: ${JSON.stringify(w)}`)
  const written = JSON.parse(fs.readFileSync(recPath, 'utf8'))
  assert.strictEqual(written.findings.length, BIG_FINDINGS.length)
  assert.strictEqual(stageRuns.length, 1, 'fencedJsonWrite stages+verifies in exactly ONE leaf (stageAndRunHelper)')
  assert.strictEqual(stageRuns[0].stagedPath, recPath + '.payload', 'the payload is staged as a file, not inline')
  const fjCall = helperCalls.find((c) => String(c[1]).includes('fenced_json.py'))
  assert.ok(fjCall, 'fencedJsonWrite went through the fenced_json.py helper')
  assert.ok(fjCall.includes('--payload-path'), 'fencedJsonWrite must pass --payload-path')
  assert.ok(fjCall.includes('--payload-hash'), 'fencedJsonWrite must self-verify the staged payload (--payload-hash)')
  assert.ok(!fjCall.includes('--payload-json'), 'fencedJsonWrite must not pass --payload-json')
  for (const arg of fjCall) assert.ok(String(arg).length <= ARG_BOUND, 'fenced write arg too large')
  assert.ok(!fs.existsSync(recPath + '.payload'), 'staged payload file consumed on success')

  // (d) #193: the RESUME read is the entry-bootstrap DECIDER — a large verbose on-disk history
  // (a couple blocking findings + many non-blocking, every body chatty) collapses to per-round
  // STUBS (blocking-only skeletons + decision scalars) that fit ONE direct payload-tier answer.
  // Entry seeding is ≤2 courier leaves (one bootstrap, one retry at most) with ZERO read-chunk
  // calls — down from the pre-#193 receipt + N ~34k-token chunk leaves (the #118 courier-collapse
  // bar). Non-blocking finding bodies AND titles never ride back.
  const rdir = fs.mkdtempSync(path.join(os.tmpdir(), 'loop-resume-'))
  const RESUME_BLOCKING = Array.from({ length: 2 }, (_, i) => ({
    file: 'a.py', line: i + 1, title: `blocker ${i}`, severity: 'Critical',
    taxonomy: 'bug', dimension: 'Code', evidence: BIG_EVIDENCE }))
  const RESUME_MINOR = Array.from({ length: 40 }, (_, i) => ({
    file: 'b.py', line: i + 1, title: `nit number ${i} with a chatty verbose body`, severity: 'Minor',
    taxonomy: 'style', dimension: 'Code', evidence: BIG_EVIDENCE }))
  const RESUME_FINDINGS = RESUME_BLOCKING.concat(RESUME_MINOR)
  const bigRecs = [1, 2].map((rnd) => ({
    schemaVersion: 2, round: rnd, kind: 'baseline', confirmationPending: false,
    changedSubjects: ['Code'], coverageDecisions: [], tokenUsage: {},
    findings: RESUME_FINDINGS, carriedFindings: [],
    dimensions: { code: { dimension: 'code', status: 'run', confidence: 'high', round: rnd, tier: 'reviewer-deep', findings: RESUME_FINDINGS, hasFindings: true, subjects: ['Code'] } },
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
  // the resume seed goes through entry-bootstrap, in ≤2 invocations, with ZERO chunk reads
  const bootstrapCalls = helperResults.filter((h) => h.args.includes('entry-bootstrap'))
  assert.ok(bootstrapCalls.length >= 1, 'the resume seed goes through entry-bootstrap')
  assert.ok(bootstrapCalls.length <= 2, `entry seeding is ≤2 leaves (one retry max), got ${bootstrapCalls.length}`)
  assert.ok(!helperResults.some((h) => h.args.includes('load-summary')),
    '#193: the resume no longer pays the full load-summary skeleton')
  const chunkReads = helperResults.filter((h) => h.args.includes('read-chunk'))
  assert.strictEqual(chunkReads.length, 0, `a bounded bootstrap needs ZERO chunk reads (got ${chunkReads.length})`)
  const seed = bootstrapCalls[0]
  assert.ok(seed.stdout.length < 4000 && seed.stdout.length < onDisk / 10,
    `resume bootstrap stdout must be a small direct answer (${seed.stdout.length}B vs ${onDisk}B on disk)`)
  const seedAnswer = JSON.parse(seed.stdout)
  assert.ok(!('receipt' in seedAnswer), 'the bounded bootstrap answers DIRECT, not as a receipt')
  assert.ok(Array.isArray(seedAnswer.records) && seedAnswer.records.length === 2, 'the bootstrap ships the two prior-round stubs')
  assert.ok(!seed.stdout.includes(BIG_EVIDENCE), 'evidence bodies never ride the bootstrap stdout')
  assert.ok(!seed.stdout.includes('nit number'), 'non-blocking finding titles never ride the bootstrap stdout')
  for (const stub of seedAnswer.records) {
    assert.deepStrictEqual(stub.findings.map((f) => f.severity), ['Critical', 'Critical'],
      'the stub keeps blocking-finding skeletons only')
  }
  const plainLoad = helperResults.find((h) =>
    String(h.args[0] || '').includes('review_memory.py') && h.args.includes('load') && !h.args.includes('load-summary'))
  assert.ok(!plainLoad, 'the full-echo review_memory load verb must not be used by the loop')

  console.log('ok: review-loop persistence ships paths + small scalars only (no mega-JSON through the courier)')
}

main().catch((e) => { console.error('FAIL:', e.message || e); process.exit(1) })
