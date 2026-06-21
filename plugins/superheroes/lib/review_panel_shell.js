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
// reviewPanel({ reviewerSet, context, rubric, runKey, runDir, fixStep, maxRounds = 7 }) -> verdict
async function reviewPanel({ reviewerSet, context, rubric, runKey, runDir, fixStep, maxRounds = 7 }) {
  if (!reviewerSet || reviewerSet.length === 0) {
    // empty roster is rejected by the core; surface its verdict without dispatching anything.
    return await tallyAgent(runDir, 1, reviewerSet, maxRounds, 'no', 'completed')
  }
  let round = 1
  while (true) {
    // 1. Fan out the panel — each reviewer writes findings-<name>.json into round-<N>/.
    await parallel(reviewerSet.map((r) => () => dispatchReviewer(r, context, rubric, runDir, round)))
    // 2. Deterministic tally (the core decides gate/confidence/terminal + writes the durable record).
    const verdict = await tallyAgent(runDir, round, reviewerSet, maxRounds, 'no', 'completed')
    // 3. The shell's only decision: stop unless the core says continue.
    if (verdict.terminal !== 'continue') return verdict
    // 4. Fix step (caller's). Detect failure/timeout; the CORE decides halted.
    const fixOk = await runFixStep(fixStep, verdict, runDir)
    if (!fixOk) {
      return await tallyAgent(runDir, round, reviewerSet, maxRounds, 'no', 'failed')
    }
    round += 1
  }
}

// Dispatch one reviewer leaf agent; UFR-1: one re-dispatch if it does not finish (a missing/
// malformed findings file is what the tally reads as "did not complete").
async function dispatchReviewer(reviewer, context, rubric, runDir, round) {
  const ok = await reviewerAgent(reviewer, context, rubric, runDir, round)
  if (!ok) await reviewerAgent(reviewer, context, rubric, runDir, round) // single re-dispatch
}

// Run panel_tally.py via a thin command-runner leaf agent; returns the parsed, schema-validated verdict.
async function tallyAgent(runDir, round, roster, maxRounds, breakerHalt, fixStatus) {
  const cmd =
    `python3 plugins/superheroes/lib/panel_tally.py --run-dir ${shq(runDir)} --round ${round} ` +
    `--roster ${shq(roster.join(','))} --max-rounds ${maxRounds} ` +
    `--breaker-halt ${shq(breakerHalt)} --fix-status ${shq(fixStatus)}`
  const out = await agent(
    `Run exactly this command and return ONLY its stdout JSON, unchanged:\n\n${cmd}`,
    { label: `tally:r${round}`, schema: VERDICT_SCHEMA }
  )
  return out
}

// Invoke the caller-supplied fix step on the round's blocking findings; record its per-finding
// resolved/deferred report into deferred-set.json (the core reads it next round). Returns false on
// fix-step failure/timeout (UFR-3) — the shell does NOT decide the outcome, the core does.
async function runFixStep(fixStep, verdict, runDir) {
  const blockers = verdict.findings.filter((f) => f.severity === 'Critical' || f.severity === 'Important')
  const report = await fixStep(blockers, runDir) // caller's leaf agent; may return null on failure
  if (!report) return false
  await recordDeferred(report, verdict, runDir) // append deferred identities (+severity) to deferred-set.json
  return true
}

const VERDICT_SCHEMA = {
  type: 'object',
  required: ['gate', 'confidence', 'findings', 'terminal'],
  properties: {
    gate: { enum: ['clean', 'blocking', 'cannot-certify'] },
    confidence: { enum: ['high', 'low'] },
    findings: { type: 'array' },
    terminal: { enum: ['continue', 'clean', 'clean-with-skips', 'cannot-certify', 'halted'] },
    reason: { type: 'string' },
  },
}

function shq(s) { return "'" + String(s).replace(/'/g, "'\\''") + "'" }

// reviewerAgent / recordDeferred are caller/runtime-provided leaf-agent wrappers; a consumer
// (#88/#89) supplies them with its real reviewer dispatch and its deferred-set writer. The harness
// (Task 8) supplies stubs.
module.exports = { reviewPanel, VERDICT_SCHEMA }
