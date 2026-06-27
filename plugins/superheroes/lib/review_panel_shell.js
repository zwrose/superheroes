// review_panel_shell.js — the reusable review-panel + loop-to-clean orchestration shell (#86).
//
// CONTROL FLOW ONLY. Every judgement (compile, gate, confidence, the four loop terminals, the
// fix-failure -> halted decision) lives in panel_tally.py; this shell detects events and forwards
// them. The shell makes exactly one branch: `if (terminal !== 'continue')`.
//
// Runtime contract (native Workflow): `agent()` runs a leaf worker (no Agent tool, §10.1);
// `parallel()` fans out. The tally runs panel_tally.py via a thin command-runner leaf agent that
// returns its JSON verdict (schema-validated). The reviewers + fixStep are caller-supplied leaf
// agents. `runKey` names the on-disk scratch dir the reviewers/tally read & write.
//
// reviewPanel({ reviewerSet, context, rubric, runKey, runDir, fixStep, maxRounds, legKind, verifyCommand })
// legKind = { panel: bool, code: bool }. CONTROL FLOW ONLY — every decision is computed in
// panel_tally.py / loop_synthesis.py / verify_gate.py (protected Python); this shell only
// detects events and forwards. The shell is itself in SAFETY_MACHINERY (FR-24).
const { io } = require('./io_seam.js')
function _usable(v) { return v && typeof v.terminal === 'string' }
function _failClosed() {
  // UFR-9 last-resort: no usable verdict from the tally -> fail closed, never a clean advance.
  return { schemaVersion: 1, terminal: 'halted', recordMissing: true,
           reason: 'tally produced no usable verdict — failing closed' }
}
async function reviewPanel({ reviewerSet, context, rubric, runKey, runDir, fixStep,
                            maxRounds = 7, legKind = {}, verifyCommand = 'none' }) {
  runDir = runDir || runKey
  if (!reviewerSet || reviewerSet.length === 0) {
    const v = await tallyAgent({ runDir, round: 1, roster: reviewerSet || [], maxRounds })
    return _usable(v) ? v : _failClosed()
  }
  let round = await resumeRound(runDir) // UFR-7: resume at the round boundary from disk
  let lastExtras = null                 // a fix step's extras (parentOrigin/escalation) ride forward
  // UFR-7: a mid-loop resume must re-load the latest fix extras (in-memory only otherwise), else the
  // resumed round's tally drops parentOrigin from the terminal record/readout.
  lastExtras = await io().readJson(`${runDir}/last-extras.json`, null)
  while (true) {
    // 1. Fan out the panel — each reviewer writes findings-<name>.json into round-<N>/.
    await parallel(reviewerSet.map((r) => () => dispatchReviewer(r, context, rubric, runDir, round)))
    // 2. Panel-only synthesis (FR-11): mechanical merge -> Opus leaf -> deterministic consume.
    // A throw from a caller-supplied merge/leaf must NOT escape before the fail-closed tally; a
    // null/failed synthesis degrades to the raw compile (keep-on-uncertain — no finding dropped),
    // logged for detectability.
    let synthesized = null
    if (legKind.panel) {
      try {
        synthesized = await synthesizeRound(reviewerSet, context, rubric, runDir, round)
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
    // 4. Deterministic tally — the core decides gate/terminal (+ internal circuit breaker). A
    // prior round's fix extras (parentOrigin/escalation) ride forward into the record/readout.
    const verdict = await tallyAgent({ runDir, round, roster: reviewerSet, maxRounds,
                                       synthesized, verifyResult, extras: lastExtras })
    if (!_usable(verdict)) return _failClosed()
    // 5. The shell's only branch: stop unless the core says continue.
    if (verdict.terminal !== 'continue') return verdict
    // 6. Fix step (caller's). Detect failure/timeout; the CORE decides halted next round.
    const fix = await runFixStep(fixStep, verdict, runDir)
    if (!fix.ok) {
      const failVerdict = await tallyAgent({ runDir, round, roster: reviewerSet, maxRounds,
                                            synthesized, verifyResult, fixStatus: 'failed', extras: fix.extras || lastExtras })
      return _usable(failVerdict) ? failVerdict : _failClosed()
    }
    lastExtras = fix.extras || lastExtras   // latest fix's extras win; persisted once a blocker is parent-traced
    // persist to a stable per-run path so a mid-loop resume can re-load it (the reload above).
    if (lastExtras) { try { await io().writeFile(`${runDir}/last-extras.json`, JSON.stringify(lastExtras)) } catch (_) {} }
    round += 1
  }
}

// Dispatch one reviewer leaf agent; UFR-1: one re-dispatch if it does not finish (a missing/
// malformed findings file is what the tally reads as "did not complete").
async function dispatchReviewer(reviewer, context, rubric, runDir, round) {
  const ok = await reviewerAgent(reviewer, context, rubric, runDir, round)
  if (!ok) await reviewerAgent(reviewer, context, rubric, runDir, round) // single re-dispatch
}

// Resume round from disk (panel_tally.resume_round — protected decision).
async function resumeRound(runDir) {
  const out = await agent(
    `Run exactly this and return ONLY its stdout, unchanged:\n\n` +
    `python3 -c 'import sys; sys.path.insert(0,"plugins/superheroes/lib"); import panel_tally; ` +
    `print(panel_tally.resume_round(sys.argv[1]))' ${shq(runDir)}`,
    { label: 'resume' })
  const n = parseInt(String(out).trim(), 10)
  return Number.isFinite(n) && n >= 1 ? n : 1
}

// Panel synthesis: mechanical merge (panel_tally.compile via the tally's own compile is reused
// by writing merged.json), then the Opus leaf, then the deterministic loop_synthesis consume.
async function synthesizeRound(reviewerSet, context, rubric, runDir, round) {
  const merged = await mergeAgent(runDir, round, reviewerSet)            // -> round-<N>/merged.json
  const leaf = await synthesisLeaf(merged, context, rubric, runDir, round) // -> round-<N>/synthesis.json
  const out = await agent(
    `Run exactly this and return ONLY its stdout JSON, unchanged:\n\n` +
    `python3 plugins/superheroes/lib/loop_synthesis.py --merged ${shq(mergedPath(runDir, round))} ` +
    `--leaf ${shq(leafPath(runDir, round))}`,
    { label: `synthesis:r${round}`, schema: SYNTH_SCHEMA })
  return out
}

// Code-leg verify gate (verify_gate.run_verify — protected classification).
async function verifyAgent(verifyCommand, runDir, round) {
  const out = await agent(
    `Run exactly this and return ONLY its stdout JSON, unchanged:\n\n` +
    `python3 plugins/superheroes/lib/verify_gate.py --command ${shq(verifyCommand || 'none')}`,
    { label: `verify:r${round}`, schema: VERIFY_SCHEMA })
  return (out && out.result) || 'fail'   // fail-closed if the runner gave nothing
}

// Run panel_tally.py via a thin command-runner leaf agent; returns the parsed, schema-validated verdict.
async function tallyAgent({ runDir, round, roster, maxRounds, synthesized = null,
                           verifyResult = null, fixStatus = 'completed', extras = null }) {
  let extra = `--breaker-halt no --fix-status ${shq(fixStatus)}`
  if (synthesized) {
    await io().mkdirp(`${runDir}/round-${round}`)   // round dir may not exist yet
    await io().writeFile(synthPath(runDir, round), JSON.stringify(synthesized))
    extra += ` --synthesized ${shq(synthPath(runDir, round))}`
  }
  if (verifyResult) extra += ` --verify-result ${shq(verifyResult)}`
  if (extras) {
    await io().mkdirp(`${runDir}/round-${round}`)   // round dir may not exist yet
    await io().writeFile(extrasPath(runDir, round), JSON.stringify(extras))
    extra += ` --extras ${shq(extrasPath(runDir, round))}`
  }
  const cmd =
    `python3 plugins/superheroes/lib/panel_tally.py --run-dir ${shq(runDir)} --round ${shq(String(round))} ` +
    `--roster ${shq((roster || []).join(','))} --max-rounds ${shq(String(maxRounds))} ${extra}`
  return await agent(
    `Run exactly this command and return ONLY its stdout JSON, unchanged:\n\n${cmd}`,
    { label: `tally:r${round}`, schema: VERDICT_SCHEMA })
}

// Invoke the caller-supplied fix step on the round's blocking findings; record its per-finding
// resolved/deferred report into deferred-set.json (the core reads it next round). Returns false on
// fix-step failure/timeout (UFR-3) — the shell does NOT decide the outcome, the core does.
async function runFixStep(fixStep, verdict, runDir) {
  try {
    const blockers = verdict.findings.filter((f) => f.severity === 'Critical' || f.severity === 'Important')
    const report = await fixStep(blockers, runDir) // caller's leaf agent; may return null on failure
    if (!report) return { ok: false, extras: null }
    await recordDeferred(report, verdict, runDir) // append deferred identities (+severity) to deferred-set.json
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
const VERIFY_SCHEMA = { type: 'object', required: ['result'],
  properties: { result: { enum: ['pass', 'fail', 'timeout', 'skipped'] } } }

// round-key path helpers (mirror panel_tally's layout)
function synthPath(d, n) { return `${d}/round-${n}/synthesized.json` }
function mergedPath(d, n) { return `${d}/round-${n}/merged.json` }
function leafPath(d, n) { return `${d}/round-${n}/synthesis.json` }
function extrasPath(d, n) { return `${d}/round-${n}/extras.json` }

function shq(s) { return "'" + String(s).replace(/'/g, "'\\''") + "'" }

// mergeAgent / synthesisLeaf / reviewerAgent / recordDeferred are caller/runtime-provided leaf
// wrappers: a consumer (#88/#89) supplies its real reviewer dispatch, its mechanical-merge writer
// (writes merged.json from the round's findings-*.json), and its Opus synthesis leaf (writes
// synthesis.json keyed by finding identity). The harness (Task 8) supplies stubs.
module.exports = { reviewPanel, VERDICT_SCHEMA, SYNTH_SCHEMA, VERIFY_SCHEMA }
