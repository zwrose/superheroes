// review_panel_shell.js — the reusable review-panel + loop-to-clean orchestration shell (#86, #115).
//
// CONTROL FLOW ONLY. Every judgement (compile, gate, confidence, the four loop terminals, the
// fix-failure -> halted decision, the circuit breaker) lives in the parity-locked pure-decider
// twins (panel_tally / loop_synthesis / circuit_breaker / loop_state); this shell detects events and
// forwards them IN MEMORY. The shell makes exactly one branch: `if (terminal !== 'continue')`.
//
// #115 re-architecture: reviewer leaves now RETURN a `findings[]` array (the panel holds them in
// memory) instead of writing findings-<name>.json. merge/synthesis-consume/tally are in-process twin
// calls over those in-memory arrays — no panel_tally.py / merge_findings.py / loop_synthesis.py
// dispatch and no per-finding disk file. The ONLY durable state is the per-round accumulator (the
// per-round verdict carrying the skip-excluded blocking finding IDENTITIES) + the deferred-set, each
// kept on disk via one cheap write so a crash-resume rebuilds the breaker history + deferred
// accounting. The synthesis leaf stays a genuine LLM agent (it returns verdicts).
//
// Runtime contract (native Workflow): `agent()` runs a leaf worker (no Agent tool, §10.1);
// `parallel()` fans out. The reviewers + synthesis leaf + fixStep are caller-supplied leaf agents.
// `runDir` names the on-disk scratch dir the accumulator + deferred-set live under.
//
// reviewPanel({ reviewerSet, context, rubric, runKey, runDir, fixStep, maxRounds, legKind, verifyCommand })
// legKind = { panel: bool, code: bool }. The shell is itself in SAFETY_MACHINERY (FR-24).
const { io } = require('./io_seam.js')
const panelTally = require('./panel_tally.js')
const loopSynthesis = require('./loop_synthesis.js')
const circuitBreaker = require('./circuit_breaker.js')
const loopState = require('./loop_state.js')
// #115 Task 16: verify gate split — subprocess run stays a cheap pipe, classification is in-process
const verifyGateTwin = require('./verify_gate.js')

const SCHEMA_VERSION = 1
const BLOCKING = new Set(['Critical', 'Important'])
const _VERIFY_OK = new Set(['pass', 'skipped'])   // none/doc-leg signalled by a null verifyResult

function _usable(v) { return v && typeof v.terminal === 'string' }
function _failClosed() {
  // UFR-9 last-resort: no usable verdict from the tally -> fail closed, never a clean advance.
  return { schemaVersion: SCHEMA_VERSION, terminal: 'halted', recordMissing: true,
           reason: 'tally produced no usable verdict — failing closed' }
}

// ── durable per-round accumulator (one cheap write per round; rebuilt on resume) ──
// Each record: { round, findings:[{file,title,severity,...}] } where findings are the round's
// compiled findings with deferred (skipped) identities removed — so a crash-resume rebuilds the
// circuit-breaker history + deferred accounting from disk. Stored as a single JSON array.
function accumulatorPath(runDir) { return `${runDir}/round-records.json` }
function deferredSetPath(runDir) { return `${runDir}/deferred-set.json` }

async function loadAccumulator(runDir) {
  const recs = await io().readJson(accumulatorPath(runDir), [])
  return Array.isArray(recs) ? recs : []
}
async function loadDeferredSet(runDir) {
  const set = await io().readJson(deferredSetPath(runDir), {})
  return (set && typeof set === 'object' && !Array.isArray(set)) ? set : {}
}

// resumeRound: the round to (re)start at = max recorded round + 1, or 1 (panel_tally.resume_round
// parity — a round is fully saved iff its accumulator record exists).
function resumeRound(records) {
  let best = 0
  for (const r of records) {
    const n = r && Number(r.round)
    if (Number.isFinite(n) && n > best) best = n
  }
  return best + 1
}

// assembleRounds: circuit_breaker's [{round, findings}] from the durable accumulator, skip-excluded
// (panel_tally.assemble_rounds parity — but reads the in-memory accumulator, not per-round files).
function assembleRounds(records, deferredSet) {
  const skip = new Set(Object.keys(deferredSet || {}))
  const out = []
  for (const rec of records) {
    if (!rec || typeof rec !== 'object') continue
    const findings = (rec.findings || []).filter((f) => !skip.has(circuitBreaker.findingIdentity(f)))
    out.push({ round: Number(rec.round), findings })
  }
  out.sort((a, b) => a.round - b.round)
  return out
}

async function reviewPanel({ reviewerSet, context, rubric, runKey, runDir, fixStep,
                            maxRounds = 7, legKind = {}, verifyCommand = 'none' }) {
  runDir = runDir || runKey
  let records = await loadAccumulator(runDir)        // durable accumulator (breaker history + deferral)
  let round = resumeRound(records)                   // UFR-7: resume at the round boundary from disk
  let lastExtras = await io().readJson(`${runDir}/last-extras.json`, null)
  // UFR-7: a mid-loop resume must re-load the latest fix extras (in-memory only otherwise), else the
  // resumed round's tally drops parentOrigin from the terminal record/readout.
  if (!reviewerSet || reviewerSet.length === 0) {
    const v = await tallyRound({ runDir, round, roster: reviewerSet || [], maxRounds,
                                 roundFindings: {}, records, legKind, verifyResult: null, extras: lastExtras })
    await persistRound(runDir, records, v)
    return _usable(v) ? v : _failClosed()
  }
  while (true) {
    // 1. Fan out the panel — each reviewer RETURNS its findings[] (held in memory, no disk file).
    const roundFindings = {}
    await parallel(reviewerSet.map((r) => () => dispatchReviewer(r, context, rubric, runDir, round, roundFindings)))
    // 2. Panel-only synthesis (FR-11): mechanical merge (compileFindings twin) -> Opus leaf -> the
    // deterministic loop_synthesis.consume twin. A throw / null synthesis degrades to the raw compile
    // (keep-on-uncertain — no finding dropped), logged for detectability.
    let synthesized = null
    if (legKind.panel) {
      try {
        synthesized = await synthesizeRound(roundFindings, context, rubric, runDir, round)
      } catch (e) {
        try { log(`review-panel r${round}: synthesis threw (${e && e.message ? e.message : e}) — falling back to raw compile`) } catch (_) {}
        synthesized = null
      }
      if (!synthesized) {
        try { log(`review-panel r${round}: synthesis produced no result — falling back to raw compile (no findings dropped)`) } catch (_) {}
      }
    }
    // 3. Code-leg verify gate (FR-17): run the project verify command, classify pass/fail/timeout.
    let verifyResult = null
    if (legKind.code) {
      try { verifyResult = await verifyAgent(verifyCommand, runDir, round) }
      catch (e) { verifyResult = 'fail' }  // fail-closed: a verify that can't run blocks clean
    }
    // 4. In-process tally — the twins decide gate/terminal (+ internal circuit breaker). A prior
    // round's fix extras (parentOrigin/escalation) ride forward into the record/readout.
    const verdict = await tallyRound({ runDir, round, roster: reviewerSet, maxRounds,
                                       roundFindings, records, legKind, synthesized, verifyResult, extras: lastExtras })
    if (!_usable(verdict)) return _failClosed()
    await persistRound(runDir, records, verdict)     // one cheap write: append this round's record
    // 5. The shell's only branch: stop unless the core says continue.
    if (verdict.terminal !== 'continue') return verdict
    // 6. Fix step (caller's). Detect failure/timeout; the CORE decides halted next round.
    const fix = await runFixStep(fixStep, verdict, runDir)
    if (!fix.ok) {
      const failVerdict = await tallyRound({ runDir, round, roster: reviewerSet, maxRounds,
                                            roundFindings, records, legKind, synthesized, verifyResult,
                                            fixStatus: 'failed', extras: fix.extras || lastExtras })
      await persistRound(runDir, records, failVerdict)
      return _usable(failVerdict) ? failVerdict : _failClosed()
    }
    lastExtras = fix.extras || lastExtras   // latest fix's extras win; persisted once a blocker is parent-traced
    // persist to a stable per-run path so a mid-loop resume can re-load it (the reload above).
    if (lastExtras) { try { await io().writeFile(`${runDir}/last-extras.json`, JSON.stringify(lastExtras)) } catch (_) {} }
    round += 1
  }
}

// One cheap durable write per round: append/replace this round's accumulator record (carrying the
// compiled findings with their blocking identities) so a crash-resume rebuilds the breaker history.
// Mutates `records` in place so the live loop's breaker history stays current without a re-read.
async function persistRound(runDir, records, verdict) {
  const rnd = Number(verdict && verdict.round)
  if (!Number.isFinite(rnd)) return
  const rec = { round: rnd, findings: (verdict.findings || []).map(
    (f) => ({ file: f.file, title: f.title, severity: f.severity })) }
  const idx = records.findIndex((r) => Number(r.round) === rnd)
  if (idx >= 0) records[idx] = rec; else records.push(rec)
  try { await io().writeFile(accumulatorPath(runDir), JSON.stringify(records)) } catch (_) {}
}

// Dispatch one reviewer leaf agent; UFR-1: one re-dispatch if it does not finish (a non-array return
// is what the tally reads as "did not complete"). On completion the RETURNED findings[] is held in
// roundFindings[reviewer]; absence of the key means the reviewer did not complete (coverage gap).
async function dispatchReviewer(reviewer, context, rubric, runDir, round, roundFindings) {
  let out = await reviewerAgent(reviewer, context, rubric, runDir, round)
  if (!Array.isArray(out)) out = await reviewerAgent(reviewer, context, rubric, runDir, round) // single re-dispatch
  if (Array.isArray(out)) roundFindings[reviewer] = out
}

// Panel synthesis: mechanical merge (panel_tally.compileFindings twin), then the genuine Opus leaf
// (returns per-finding keep/drop verdicts), then the deterministic loop_synthesis.consume twin.
async function synthesizeRound(roundFindings, context, rubric, runDir, round) {
  const all = []
  for (const arr of Object.values(roundFindings)) if (Array.isArray(arr)) all.push(...arr)
  const merged = panelTally.compileFindings(all, null)            // in-memory mechanical merge
  const leafVerdicts = await synthesisLeaf(merged, context, rubric, runDir, round) // genuine agent
  return loopSynthesis.consume(merged, Array.isArray(leafVerdicts) ? leafVerdicts : []) // {findings, drops}
}

// Code-leg verify gate split (#115 Task 16): agent runs the subprocess (--emit-run, IO-only);
// verifyGateTwin.classify maps the raw run data to pass/fail/timeout/skipped in-process.
// Fail-closed: if the agent gives nothing or the result is unparseable -> 'fail'.
async function verifyAgent(verifyCommand, runDir, round) {
  const out = await agent(
    `Run exactly this and return ONLY its stdout JSON, unchanged:\n\n` +
    `python3 plugins/superheroes/lib/verify_gate.py --command ${shq(verifyCommand || 'none')} --emit-run`,
    { label: `verify:r${round}`, schema: VERIFY_SCHEMA })
  if (!out) return 'fail'  // fail-closed if the runner gave nothing
  return verifyGateTwin.classify({ command: out.command, returncode: out.returncode, timedOut: out.timedOut })
}

// In-process tally — the parity-locked twins decide gate/confidence/terminal + the circuit breaker,
// over the in-memory roundFindings + the durable accumulator. NO panel_tally.py dispatch. Mirrors
// panel_tally.tally's precedence exactly; fails closed to `halted` on any unforeseen error (UFR-9).
async function tallyRound({ runDir, round, roster, maxRounds, roundFindings = {}, records = [],
                           legKind = {}, synthesized = null, verifyResult = null,
                           fixStatus = 'completed', extras = null }) {
  // Only readout-enrichment keys ride in from the caller — never decision/terminal fields, so a
  // caller's extras can't overwrite a fail-closed `halted` or any gate field (panel_tally parity).
  const safeExtras = {}
  if (extras && typeof extras === 'object') {
    for (const k of ['fixes', 'deferred', 'parentOrigin']) if (k in extras) safeExtras[k] = extras[k]
  }
  try {
    if (!roster || roster.length === 0) {
      return Object.assign({ schemaVersion: SCHEMA_VERSION, gate: 'cannot-certify', confidence: 'low',
        findings: [], missing: [], drops: [], terminal: 'cannot-certify', round,
        reason: 'empty reviewer set — nothing to certify' }, safeExtras)
    }
    const completed = roster.filter((r) => Array.isArray(roundFindings[r]))
    let compiled, drops
    if (synthesized && typeof synthesized === 'object') {       // panel leg: judgment already done
      compiled = synthesized.findings || []
      drops = synthesized.drops || []
    } else {                                                    // single-reviewer leg: compile raw
      const all = []
      for (const r of completed) all.push(...roundFindings[r])
      compiled = panelTally.compileFindings(all, null)
      drops = []
    }
    const gateOut = panelTally.roundGate(compiled, roster, completed)
    const gate = gateOut.gate, confidence = gateOut.confidence, missing = gateOut.incomplete
    const deferredSet = await loadDeferredSet(runDir)
    const presentBlocking = compiled.filter((f) => BLOCKING.has(f.severity)).length
    const pdef = panelTally.presentDeferred(compiled, deferredSet)
    // Internal circuit breaker (UFR-2): prior rounds from the durable accumulator + this round's
    // findings, skip-set excluded. Exclude THIS round from the disk-read history (it may already be
    // recorded from a prior idempotent call) and append the current findings exactly once.
    const skip = new Set(Object.keys(deferredSet))
    const prior = assembleRounds(records, deferredSet).filter((r) => r.round !== round)
    const thisRound = { round, findings: compiled.filter((f) => !skip.has(circuitBreaker.findingIdentity(f))) }
    const brk = circuitBreaker.checkCircuitBreaker(prior.concat([thisRound]), maxRounds)
    const breakerHalt = !!brk.halt
    let { terminal, reason } = panelTally.decideTerminal(
      gate, presentBlocking, pdef, fixStatus, round, maxRounds, breakerHalt)
    // The breaker's own reason (recurring-finding / no-net-progress / max-iterations) is the precise
    // recurrence detail the readout needs — surface it when the breaker is what forced the halt.
    if (terminal === 'halted' && breakerHalt && brk.detail) reason = brk.detail
    // Verify gate (FR-17/UFR-4): a code leg's clean terminal requires verify to have passed.
    if ((terminal === 'clean' || terminal === 'clean-with-skips') &&
        verifyResult !== null && !_VERIFY_OK.has(verifyResult)) {
      terminal = 'halted'
      reason = verifyResult === 'timeout'
        ? 'verify command timed out — cannot certify clean'
        : 'verify command failed — cannot certify clean'
    }
    if (terminal === 'cannot-certify' && missing.length) {
      reason = 'coverage incomplete — missing review angle(s): ' + missing.join(', ')
    }
    return Object.assign({ schemaVersion: SCHEMA_VERSION, gate, confidence, findings: compiled,
      missing, drops, terminal, reason, round }, safeExtras)
  } catch (exc) {   // absolute fail-safe — any unforeseen error halts, never clean (UFR-9)
    return Object.assign({ schemaVersion: SCHEMA_VERSION, gate: 'cannot-certify', confidence: 'low',
      findings: [], missing: [], drops: [], terminal: 'halted', round,
      reason: 'tally failed: ' + (exc && exc.message ? exc.message : exc) }, safeExtras)
  }
}

// Invoke the caller-supplied fix step on the round's blocking findings; record its per-finding
// resolved/deferred report into the deferred-set (the tally reads it next round). Returns false on
// fix-step failure/timeout (UFR-3) — the shell does NOT decide the outcome, the core does.
async function runFixStep(fixStep, verdict, runDir) {
  try {
    const blockers = (verdict.findings || []).filter((f) => f.severity === 'Critical' || f.severity === 'Important')
    const report = await fixStep(blockers, runDir) // caller's leaf agent; may return null on failure
    if (!report) return { ok: false, extras: null }
    await recordDeferred(report, verdict, runDir) // append deferred identities (+severity) to deferred-set
    return { ok: true, extras: (report && report.extras) || null }
  } catch (e) {
    try { log(`review-panel: fix step failed, treating as fix failure -> halted: ${e && e.message ? e.message : e}`) } catch (_) {}
    return { ok: false, extras: null }
  }
}

const VERDICT_SCHEMA = {
  type: 'object',
  required: ['terminal'],
  properties: {
    schemaVersion: { type: 'number' },
    gate: { enum: ['clean', 'blocking', 'cannot-certify'] },
    confidence: { enum: ['high', 'low'] },
    findings: { type: 'array' },
    drops: { type: 'array' },
    terminal: { enum: ['continue', 'clean', 'clean-with-skips', 'cannot-certify', 'halted'] },
    reason: { type: 'string' },
    recordMissing: { type: 'boolean' },
  },
}
const SYNTH_SCHEMA = { type: 'object', required: ['findings', 'drops'],
  properties: { findings: { type: 'array' }, drops: { type: 'array' } } }
// #115 Task 16: VERIFY_SCHEMA now matches the --emit-run output (raw run data, not classified result)
const VERIFY_SCHEMA = { type: 'object', required: ['command'],
  properties: { command: {}, returncode: {}, timedOut: {} } }

function shq(s) { return "'" + String(s).replace(/'/g, "'\\''") + "'" }

// reviewerAgent / synthesisLeaf / recordDeferred are caller/runtime-provided leaf wrappers: a
// consumer (#88/#89/#87) supplies its real reviewer dispatch (which RETURNS a findings[] array), its
// genuine Opus synthesis leaf (RETURNS per-finding keep/drop verdicts), and its deferred-set writer
// (writes the deferred identities via its own cheap executor). The harness (Task 8) supplies stubs.
module.exports = { reviewPanel, VERDICT_SCHEMA, SYNTH_SCHEMA, VERIFY_SCHEMA }
