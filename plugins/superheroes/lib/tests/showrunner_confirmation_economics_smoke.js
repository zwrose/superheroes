// Smoke: #174 confirmation-bar economics in the spine loop. A full confirmation panel that
// surfaces NEW findings no longer forfeits certification — the findings are fixed + scope-verified
// and the loop certifies, UNLESS the confirmation surfaced a Critical or its rework was
// cross-cutting (then one more full confirmation, capped at 2; a Critical at the cap parks).
// Run: node plugins/superheroes/lib/tests/showrunner_confirmation_economics_smoke.js
const assert = require('assert')
const fs = require('fs'); const os = require('os'); const path = require('path')
const { reviewPanel } = require('../review_panel_shell.js')

global.parallel = async (thunks) => Promise.all(thunks.map((t) => t()))
global.log = () => {}
global.synthesisLeaf = async () => ({ verdicts: [], usage: { total: 1 } })
global.recordDeferred = async () => {}
global.agent = async () => null

function freshDir() { return fs.mkdtempSync(path.join(os.tmpdir(), 'confecon-')) }

function receipt(runId, round) {
  return { artifact: `${runId}:round-${round}`,
    chain: [{ step: 'citation', evidence: 'c' }, { step: 'reachability', evidence: 'r' },
      { step: 'missing-check', evidence: 'm' }, { step: 'tooling', evidence: 't' }],
    coverageDecisionIds: [] }
}
function cleanResult(runDir, round) {
  return { findings: [], confidence: 'high', verificationReceipt: receipt(runDir, round), usage: { total: 1 } }
}
function findingResult(runDir, round, severity) {
  return { findings: [{ file: 'c.py', line: 3, title: `new ${severity} from confirmation`, severity, evidence: 'x' }],
    confidence: 'high', verificationReceipt: receipt(runDir, round), usage: { total: 1 } }
}
const BASELINE_BLOCKER = { file: 'a.py', line: 1, title: 'baseline blocker', severity: 'Critical', evidence: 'x' }
function baselineResult(runDir, round) {
  return { findings: [BASELINE_BLOCKER], confidence: 'high', verificationReceipt: receipt(runDir, round), usage: { total: 1 } }
}

function base(dir) {
  return {
    reviewerSet: ['test-reviewer', 'security-reviewer'], context: {}, rubric: 'r', runKey: dir, runDir: dir,
    fixStep: async () => ({ fixed: ['fixed'], changedSubjects: ['Test'], coverageDecisions: [] }),
    maxRounds: 12, legKind: { panel: true, code: false },
  }
}

// Drive the loop, returning findings for the primary reviewer keyed by (round, roundKind); the
// nth confirmation panel surfaces `confirmationSurfaces[n-1]` (a severity, or null for clean).
function driver(dir, confirmationSurfaces) {
  let confirmations = 0
  const confirmationRounds = []
  const g = {
    reviewerAgent: async (_r, _c, _rub, runDir, round, opts) => {
      const kind = opts && opts.roundKind
      if (round === 1) return baselineResult(runDir, round)
      if (kind === 'confirmation') {
        // count each distinct confirmation round once (per-round, not per-reviewer)
        if (!confirmationRounds.includes(round)) { confirmationRounds.push(round); confirmations += 1 }
        const sev = confirmationSurfaces[confirmations - 1]
        // only the first reviewer surfaces the finding; keep it a single blocker
        if (sev && _r === 'test-reviewer') return findingResult(runDir, round, sev)
        return cleanResult(runDir, round)
      }
      return cleanResult(runDir, round)
    },
    confirmationCount: () => confirmationRounds.length,
  }
  return g
}

async function run(dir, confirmationSurfaces, opts = {}) {
  const g = driver(dir, confirmationSurfaces)
  global.reviewerAgent = g.reviewerAgent
  const v = await reviewPanel({ ...base(dir), ...opts })
  return { v, confirmations: g.confirmationCount() }
}

async function main() {
  // 1. A confirmation that surfaces a NEW Important certifies after a scoped verify — no 2nd panel.
  {
    const { v, confirmations } = await run(freshDir(), ['Important', null, null])
    assert.strictEqual(v.terminal, 'clean', '1: non-Critical confirmation finding still certifies')
    assert.strictEqual(confirmations, 1, '1: exactly ONE full confirmation panel runs (no re-arm)')
    assert.ok(v.certification && v.certification.fullPanels === 1, '1: readout records 1 full panel')
    assert.strictEqual(v.certification.lastPanelSurfacedResolved, true,
      '1: readout is honest that the last panel surfaced findings resolved by scoped verify')
  }

  // 2. A confirmation that surfaces a Critical triggers exactly one more full confirmation.
  {
    const { v, confirmations } = await run(freshDir(), ['Critical', null, null])
    assert.strictEqual(v.terminal, 'clean', '2: Critical confirmation finding certifies after 2nd panel')
    assert.strictEqual(confirmations, 2, '2: a Critical re-arms exactly one more full confirmation panel')
    assert.strictEqual(v.certification.fullPanels, 2, '2: readout records 2 full panels')
  }

  // 3. Hard cap: a Critical surfaced at the 2nd (cap) confirmation parks — certification withheld.
  {
    const { v, confirmations } = await run(freshDir(), ['Critical', 'Critical', 'Critical'])
    assert.strictEqual(v.terminal, 'halted', '3: a Critical at the confirmation cap parks (fail-safe)')
    assert.strictEqual(confirmations, 2, '3: never more than 2 full confirmation panels')
    assert.match(v.reason || '', /cap/, '3: park reason names the confirmation cap')
  }

  console.log('ok: #174 confirmation-bar economics — certify-after-scoped, severity re-arm, hard cap')
}

main().catch((e) => { console.error('FAIL:', e.message || e); process.exit(1) })
